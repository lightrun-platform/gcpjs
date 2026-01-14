const functions = require('@google-cloud/functions-framework');
const lightrun = require('lightrun/gcp');

let requestCount = 0;
let allTimeStats = { totalPosts: 0, totalScore: 0, topPost: null };

const lightrunSecret = process.env.LIGHTRUN_SECRET;
if (!lightrunSecret || lightrunSecret.trim() === '') {
    throw new Error('LIGHTRUN_SECRET environment variable is required and cannot be empty');
}

const displayName = process.env.DISPLAY_NAME;
if (!displayName || displayName.trim() === '') {
    throw new Error('DISPLAY_NAME environment variable is required and cannot be empty');
}

lightrun.init({
    lightrunSecret: lightrunSecret,
    agentLog: { agentLogTargetDir: '', agentLogLevel: 'warn' },
    internal: { gcpDebug: true },
    metadata: { registration: { displayName: 'Hacker-News-Lightrun-Report-' + displayName } }
});

async function fetchHackerNewsPosts(postsCount = 5) {
    // Fetch top story IDs
    const topStoriesRes = await fetch('https://hacker-news.firebaseio.com/v0/topstories.json');
    if (!topStoriesRes.ok) throw new Error(`HN error: ${topStoriesRes.status}`);
    const storyIds = await topStoriesRes.json();
    
    // Fetch details for top N stories
    const topIds = storyIds.slice(0, postsCount);
    const stories = await Promise.all(
        topIds.map(id => 
            fetch(`https://hacker-news.firebaseio.com/v0/item/${id}.json`).then(r => r.json())
        )
    );
    
    return stories;
}

function analyzePost(post) {
    const title = post.title || '';
    const wordCount = title.split(/\s+/).filter(w => w.length > 0).length;
    return {
        title,
        author: post.by,
        score: post.score || 0,
        comments: post.descendants || 0,
        url: post.url,
        wordCount,
        hasQuestion: title.includes('?'),
        engagement: (post.score || 0) + ((post.descendants || 0) * 10)
    };
}

function computeStats(posts) {
    const totalScore = posts.reduce((sum, p) => sum + p.score, 0);
    const totalComments = posts.reduce((sum, p) => sum + p.comments, 0);
    const topByEngagement = [...posts].sort((a, b) => b.engagement - a.engagement)[0];
    return { totalPosts: posts.length, totalScore, totalComments, topByEngagement: topByEngagement?.title };
}

functions.http('fetchHackerNews', lightrun.wrap(async (req, res) => {
    requestCount++;
    const postsCount = parseInt(req.query.postsCount) || 5;
    
    try {
        const startTime = Date.now();
        const rawPosts = await fetchHackerNewsPosts(postsCount);
        const fetchDuration = Date.now() - startTime;
        
        const analyzedPosts = rawPosts.map(analyzePost);
        const stats = computeStats(analyzedPosts);
        
        allTimeStats.totalPosts += stats.totalPosts;
        allTimeStats.totalScore += stats.totalScore;
        
        res.json({ 
            requestCount, 
            postsCount, 
            fetchMs: fetchDuration,
            source: 'Hacker News',
            stats, 
            allTimeStats, 
            posts: analyzedPosts 
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
}));
