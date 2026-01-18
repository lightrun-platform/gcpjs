let isColdStart = true;
const startTime = process.hrtime.bigint()

const functions = require('@google-cloud/functions-framework');

const gcfImportEndTime = process.hrtime.bigint()

const lightrunSecret = process.env.LIGHTRUN_SECRET;
if (!lightrunSecret || lightrunSecret.trim() === '') {
  throw new Error('LIGHTRUN_SECRET environment variable is required');
}

const initPhaseEnd = process.hrtime.bigint()


functions.http('helloNoLightrun', async (req, res) => {
  const handlerStartTime = process.hrtime.bigint()

  const gcfImportDuration = gcfImportEndTime - startTime;
  const totalImportsDuration = gcfImportDuration;
  const envCheckDuration = initPhaseEnd - gcfImportEndTime;
  const totalSetupDuration = initPhaseEnd - startTime;
  const functionInvocationOverhead = handlerStartTime - initPhaseEnd;
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
  `Hello, not using Lightrun!
      Total duration: ${formatDuration(totalDuration)}
      Total imports duration: ${formatDuration(totalImportsDuration)}
      GCF import duration: ${formatDuration(gcfImportDuration)}
      envCheckDuration duration: ${formatDuration(envCheckDuration)}
      Total setup duration: ${formatDuration(totalSetupDuration)}
      Function invocation overhead: ${formatDuration(functionInvocationOverhead)}`;

    res.send({
      isColdStart: isColdStart,
      message: message,
      totalDuration: totalDuration.toString(),
      totalImportsDuration: totalImportsDuration.toString(),
      gcfImportDuration: gcfImportDuration.toString(),
      envCheckDuration: envCheckDuration.toString(),
      totalSetupDuration: totalSetupDuration.toString(),
      functionInvocationOverhead: functionInvocationOverhead.toString()
  });
  isColdStart = false;
});