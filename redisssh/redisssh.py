'''
A redis-py Connection subclass that tunnels over SSH, and a redis.ConnectionPool
which allows pooled RedisSSHConnections to share the same SSH connnection.
If you prefer not to share one SSHClient connection for all pooled collections,
and have each connection in the pool tunnel over it's own SSH connection, then
use

redis.ConnectionPool(
	connection_class = RedisSSHConnection,
	ssh_host = "...",
	ssh_user = "...",
	ssh_key = "...",
	...)

External dependencies are just paramiko for ssh.

Paramiko was chosen because it is a pure-python library and thus more portable than 
an approach that requires a binary shared library, or an external executablen that is
run with stdio redirected in a child process.

This source code is distributed under an MIT license.
Happy hacking.

- Victor M. Condino <un1tz3r0@gmail.com> <vic@cor3.llc>
Sat 20 Feb 2021 07:47:01 AM EST
'''

import redis
import paramiko
import os

class RedisSSHConnectionPool(redis.ConnectionPool):
		def __init__(self, *args, ssh_client=None, ssh_shared=True, **kwargs):
				''' a redis-py connection pool of RedisSSHConnection instances which may share
				an SSHClient. if ssh_shared is True (default), then the pool creates a single 
				paramiko.SSHClient and passes it to the RedisSSHConnection instances upon 
				construction. '''
				if ssh_client == None and ssh_shared:
					self.ssh_client = paramiko.SSHClient()
				else:
					self.ssh_client = ssh_client
				super(RedisSSHConnectionPool, self).__init__(connection_class=RedisSSHConnection, ssh_client=self.ssh_client, **kwargs)


class RedisSSHConnection(redis.Connection):

		def __init__(self,
				ssh_host: str = None,
				ssh_port: int = 22,
				ssh_user: str = os.getlogin(),
				ssh_key: (str, bytes, paramiko.PKey) = os.path.expanduser("~/.ssh/id_rsa"),
				ssh_rhost: str = "127.0.0.1",
				ssh_rport: int = 6379,
				ssh_client: paramiko.SSHClient = None,
				**kwargs: ''' rest of arguments are passed to the super class constructor redis.Connection '''
			):

			# parameters used to initialize and connect a new SSHClient instance if we are not sharing the one
			# passed to us in ssh_client.
			self.ssh_host = ssh_host
			self.ssh_port = ssh_port
			self.ssh_key = ssh_key
			self.ssh_user = ssh_user

			# parameters used to connect to redis on the remote host
			self.ssh_rhost = ssh_rhost
			self.ssh_rport = ssh_rport
			self.ssh_client = ssh_client

			# set to the socket-like channel object representing the tunneled redis connection once _connect()
			# has been called successfully
			self.ssh_channel = None

			super(RedisSSHConnection, self).__init__(**kwargs)

		def _connect(self):
			if self.ssh_client == None:
				ssh = paramiko.SSHClient()
				self.ssh_client = ssh
			else:
				ssh = self.ssh_client

			if ssh.get_transport() == None or not ssh.get_transport().is_active():
				# self.ssh_client, either first use of a shared instance or an instance
				# we just created ourself (because no shared instance was passed into our
				# __init__) is not yet connected... use the connection info specified to
				# __init__ to connect
				if isinstance(self.ssh_key, str):
					try:
						pk = paramiko.RSAKey.from_private_key_file(os.path.expanduser(self.ssh_key))
					except Exception as err:
						raise redis.RedisError(f"Error reading SSH private key file: {str(err)}")
				elif isinstance(self.ssh_key, bytes):
					try:
						pk = paramiko.RSAKey.from_private_key_blob(self.ssh_key)
					except Exception as err:
						raise redis.RedisError(f"Error loading SSH private key blob: {str(err)}")
				elif isinstance(self.ssh_key, paramiko.PKey):
					pk = self.ssh_key
				else:
					raise redis.RedisError(f"Error, ssh_key must be either a str (path to id_rsa private key file), bytes (contents of id_rsa private key), or an instance of paramiko.PKey. Note that str and bytes expect RSA private key data, if you wish to use another cipher please load the key yourself and pass in the paramiko.PKey subclass instance.")

				# at this point we should be ready to call connect
				try:
					ssh.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
					ssh.load_system_host_keys()
					ssh.connect(pkey=pk, hostname=self.ssh_host, username=self.ssh_user) #key_filename=os.path.expanduser(self.ssh_keyfile))
				except Exception as err:
					raise redis.RedisError(f"Error opening SSH connection: {str(err)}")

			try:
				channel = ssh.get_transport().open_channel(dest_addr=(self.ssh_rhost, self.ssh_rport), src_addr=("", 0xfffe), kind="direct-tcpip")
			except Exception as err:
				raise redis.RedisError(f"Error opening SSH channel: {str(err)}")

			self.ssh_channel = channel
			return channel

