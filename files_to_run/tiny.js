require('http')
  .createServer((req, res) => { res.end('ok'); })
  .listen(3005, '127.0.0.1', () => console.log('listening on 127.0.0.1:3005'));
