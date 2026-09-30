# README figures and demo previews

The two radar figures use [the official demo's seven-category scores](https://index-translate.bilibili.com/?p=/site/assets/blog/seven_category_scores_raw.csv), saved as `seven_category_scores_raw.csv`. These are category aggregates for text models, not the separate NativeLong or Echo evaluations and not the individual columns of the report's main benchmark table.

For each category, every plotted value uses `100 * (score - min) / (max - min)`, where `min` and `max` are computed across all models in the saved CSV. The two Index models, DeepSeek-V4.1-Flash, and GPT-5.6-Sol are the demo's default comparison curves. The dashed envelope is the best non-Index value in each category, including models not drawn individually. It is not one actual model. Distances and polygon areas must not be interpreted as raw score differences. No Index-Translate-35B-A3B curve is inferred.

Reproduce with Python, matplotlib, and numpy:

```bash
python docs/assets/render_radar.py --language en
python docs/assets/render_radar.py --language zh --font /path/to/a/CJK/font.ttf
```

`echo-s2st.png` and `echo-s2tt.png` are previews of the official demo videos. Their README links open the hosted MP4 files; no video binaries are stored here.

- [Speech-to-speech video](https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo.mp4)
- [Multilingual subtitle video](https://index-translate.bilibili.com/?p=/site/assets/blog/echo-demo-s2tt.mp4)

七维图使用官网的文本模型聚合分数，采用固定的逐维 min–max 归一化。灰色虚线是各维度非 Index 模型最高值的组合，不对应单一模型。完整原始分数保留在 CSV 中；图形距离和面积不能当作原始分差。视频预览图链接到官网 MP4。
