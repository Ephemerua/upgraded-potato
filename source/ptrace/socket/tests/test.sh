gcc ../../ptrace.c -o ./ptrace
gcc ./server.c -o server
gcc ./client.c -o client
./ptrace ./server 
