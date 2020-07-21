frida-trace -f test1/server -S socket.js
# run test1/client in another terminal
frida-trace -f test2/server -S socket.js
# run test2/client in another terminal
frida-trace -f test3/server -S socket.js
# run test3/client in another terminal

