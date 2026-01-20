const functions = require('@google-cloud/functions-framework');
const lightrun = require('lightrun/gcp');

lightrun.init({
  lightrunSecret: "65cf112e-03f5-42da-a2f3-3c46d368872b",
  metadata: {
    registration: {
      displayName: 'NC'
    }
  }
});

functions.http('helloHttp', lightrun.wrap(async (req, res) => {
  const name = req.query.name || req.body.name || 'World';
  res.send(`Hello, ${name}!`);
}


));