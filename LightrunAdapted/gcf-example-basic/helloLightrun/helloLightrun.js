let isColdStart = true;
const startTime = process.hrtime.bigint()

const functions = require('@google-cloud/functions-framework');
const gcfImportEndTime = process.hrtime.bigint()
const lightrun = require('lightrun/gcp');
const lightrunImportEndTime = process.hrtime.bigint()

const lightrunSecret = process.env.LIGHTRUN_SECRET;
if (!lightrunSecret || lightrunSecret.trim() === '') {
  throw new Error('LIGHTRUN_SECRET environment variable is required');
}

const displayName = process.env.DISPLAY_NAME;
if (!displayName || displayName.trim() === '') {
  throw new Error('DISPLAY_NAME environment variable is required and cannot be empty');
}

const lightrunInitStart = process.hrtime.bigint()
lightrun.init({
  lightrunSecret: lightrunSecret,
  metadata: {
    registration: {
      displayName: displayName
    }
  }
});
const lightrunInitEnd = process.hrtime.bigint()


functions.http('helloLightrun', lightrun.wrap(async (req, res) => {
  const handlerStartTime = process.hrtime.bigint()

  const lightrunImportDuration = lightrunImportEndTime - gcfImportEndTime;
  const gcfImportDuration = gcfImportEndTime - startTime;
  const totalImportsDuration = lightrunImportDuration + gcfImportDuration;
  const envCheckDuration = lightrunInitStart - lightrunImportEndTime;
  const lightrunInitDuration = lightrunInitEnd - lightrunInitStart;
  const totalSetupDuration = lightrunInitEnd - startTime;
  const functionInvocationOverhead = handlerStartTime - lightrunInitEnd;
  const totalDuration = handlerStartTime - startTime;

  const formatDuration = (nanoseconds) => {
    // Use BigInt literals (n) to maintain absolute precision
    const ns = BigInt(nanoseconds);
  
    const seconds = ns / 1_000_000_000n;
    const milliseconds = (ns % 1_000_000_000n) / 1_000_000n;
    const microseconds = (ns % 1_000_000n) / 1_000n;
    const remainingNs = ns % 1_000n;
  
    const parts = [];
    if (seconds > 0n) parts.push(`${seconds}s`);
    if (milliseconds > 0n) parts.push(`${milliseconds}ms`);
    if (microseconds > 0n) parts.push(`${microseconds}µs`);
    if (remainingNs > 0n || parts.length === 0) parts.push(`${remainingNs}ns`);
  
    return parts.join(', ');
  };


  const message = 
  `Hello from Lightrun!
      Total duration: ${formatDuration(totalDuration)}
      Total imports duration: ${formatDuration(totalImportsDuration)}
      Lightrun import duration: ${formatDuration(lightrunImportDuration)}
      GCF import duration: ${formatDuration(gcfImportDuration)}
      envCheckDuration duration: ${formatDuration(envCheckDuration)}
      Lightrun initialization duration: ${formatDuration(lightrunInitDuration)}
      Total setup duration: ${formatDuration(totalSetupDuration)}
      Function invocation overhead: ${formatDuration(functionInvocationOverhead)}`;

    res.send({
      isColdStart: isColdStart,
      message: message,
      totalDuration: totalDuration.toString(),
      totalImportsDuration: totalImportsDuration.toString(),
      lightrunImportDuration: lightrunImportDuration.toString(),
      gcfImportDuration: gcfImportDuration.toString(),
      envCheckDuration: envCheckDuration.toString(),
      lightrunInitDuration: lightrunInitDuration.toString(),
      totalSetupDuration: totalSetupDuration.toString(),
      functionInvocationOverhead: functionInvocationOverhead.toString()
  });
  isColdStart = false;
}
)); 