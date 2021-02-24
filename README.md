# redisssh

SSH tunnels for your redis.Connection and redis.ConnectionPool, using Paramiko

This module allows you to connect to a remote redis server without having to rely on redis 
for authentication and security. It should be a drop-in replacement for code that's already 
using the standard redis-py module's Connection and ConnectionPool classes, just add the ssh
connection keyword-arguments or use the sane defaults.

# Multiplexing

RedisSSHConnectionPool can work in one of two ways:

1. Non-shared, where each redis connection has it's own SSH client connection with a single
forwarded channel. To use this behavior, pass the constructor keyword argument ssh_shared=False

    # <code example>

2. Shared, where there is a single SSH client connection for the ConnectionPool instance, and 
the connections in the pool are multiplexed each on it's own channel.

    # <code example>

Which of these is right for you depends on a number of factors, and on how your application 
makes use of redis.
