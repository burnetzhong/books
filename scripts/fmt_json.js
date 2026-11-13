// 按网页保存时的格式重排 JSON（键排序、两格缩进），避免无意义的差异。
// 用法：node scripts/fmt_json.js docs/data/ratings.json docs/data/paper.json
const fs = require('fs');
const stable = v => Array.isArray(v) ? v.map(stable)
  : (v && typeof v === 'object') ? Object.fromEntries(Object.keys(v).sort().map(k => [k, stable(v[k])])) : v;
for (const f of process.argv.slice(2)) {
  fs.writeFileSync(f, JSON.stringify(stable(JSON.parse(fs.readFileSync(f, 'utf8'))), null, 2) + '\n');
}
