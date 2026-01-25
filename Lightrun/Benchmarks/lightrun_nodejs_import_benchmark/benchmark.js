const Module = require('module');
const originalRequire = Module.prototype.require;
const path = require('path');
const fs = require('fs');

// Centralized results directory: ../../benchmark_results/<BenchmarkName>/<TIMESTAMP>
const BENCHMARK_NAME = path.basename(__dirname);
const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
const resultsDir = path.resolve(__dirname, '../../benchmark_results', BENCHMARK_NAME, timestamp);

if (!fs.existsSync(resultsDir)) {
    fs.mkdirSync(resultsDir, { recursive: true });
}

console.log(`Results will be saved to: ${resultsDir}`);

// Tree node structure
class Node {
    constructor(id) {
        this.id = id;
        this.totalDuration = 0;
        this.childrenDuration = 0;
        this.selfDuration = 0;
        this.children = [];
        this.depth = 0;
    }
}

// Root pseudo-node
const root = new Node('ROOT');
let currentNode = root;

Module.prototype.require = function (id) {
    const start = process.hrtime.bigint();

    // Resolve filename for better ID
    let filename = id;
    try {
        filename = Module._resolveFilename(id, this);
    } catch (e) { }

    // Create new node and attach to tree
    const childNode = new Node(filename);
    childNode.depth = currentNode.depth + 1;
    currentNode.children.push(childNode);

    const parentNode = currentNode;
    currentNode = childNode;

    try {
        return originalRequire.apply(this, arguments);
    } finally {
        const end = process.hrtime.bigint();
        const duration = Number(end - start) / 1e6; // ms

        childNode.totalDuration = duration;

        // Calculate children duration by summing their total durations
        childNode.childrenDuration = childNode.children.reduce((sum, child) => sum + child.totalDuration, 0);

        // Self duration
        childNode.selfDuration = childNode.totalDuration - childNode.childrenDuration;

        // Pop stack
        currentNode = parentNode;
    }
};

console.log('--- STARTING REQUIRE ---');
const totalStart = process.hrtime.bigint();

require('lightrun/gcp');

const totalEnd = process.hrtime.bigint();
const totalDuration = Number(totalEnd - totalStart) / 1e6;

console.log(`--- DONE in ${totalDuration.toFixed(2)}ms ---\n`);

console.log('Format: [Self Time] + [Children Time] = [Total Time]  File Path');
console.log('-'.repeat(100));

// Recursive print function
function printTree(node) {
    // Skip ROOT node itself, but process children
    if (node === root) {
        node.children.forEach(printTree);
        return;
    }

    // Only process node_modules (based on user preference/context)
    if (node.id.includes('node_modules')) {
        const relPath = node.id.split('node_modules/').pop();
        const indent = '  '.repeat(Math.max(0, node.depth - 1));

        // Using padStart for alignment
        const selfStr = node.selfDuration.toFixed(2).padStart(7);
        const childStr = node.childrenDuration.toFixed(2).padStart(7);
        const totalStr = node.totalDuration.toFixed(2).padStart(8);

        console.log(`${selfStr}ms + ${childStr}ms = ${totalStr}ms  ${indent}${relPath}`);
    } else {
        // Even if not node_modules, we might want to show it or at least traverse children
        // For this test, likely everything interesting is in node_modules
        // But let's print everything just in case, or decide based on user previous logic
        // User logic was: if (filename.includes('node_modules')) ...
        // But we must traverse children regardless!
        // If we don't print this node, we still print children?
        // Yes, otherwise tree is broken visually.
        // But if we hide this node, indentation of children might be confusing.
        // Let's just print everything, but maybe dim non-node_modules? 
        // For simplicity and matching user request, let's just print everything if it has duration.

        const indent = '  '.repeat(Math.max(0, node.depth - 1));
        const selfStr = node.selfDuration.toFixed(2).padStart(7);
        const childStr = node.childrenDuration.toFixed(2).padStart(7);
        const totalStr = node.totalDuration.toFixed(2).padStart(8);
        // console.log(`${selfStr}ms + ${childStr}ms = ${totalStr}ms  ${indent}${node.id}`);
    }

    node.children.forEach(printTree);
}

printTree(root);
