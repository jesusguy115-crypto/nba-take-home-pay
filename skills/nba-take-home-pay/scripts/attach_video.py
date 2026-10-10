"""Attach a verified local MP4 to the exact saved query; use after encoding its scenes."""
import argparse,json,hashlib
from pathlib import Path
from render_chart import write_chart
p=argparse.ArgumentParser(description=__doc__);p.add_argument('query',type=Path);p.add_argument('video',type=Path);a=p.parse_args()
v=a.video.resolve();meta=json.loads(v.with_suffix('.verification.json').read_text())
if not meta.get('cfr_verified') or not v.is_file():raise ValueError('缺少通过验证的视频')
# Require the operator to encode this query's studio; do not discover similarly named files.
data=json.loads(a.query.read_text())
studio=Path(data['story_pack']['studio']);manifest=meta.get('frame_manifest') or {}
if manifest.get('studio_sha256')!=hashlib.sha256(studio.read_bytes()).hexdigest():raise ValueError('视频与当前素材页不匹配，必须重新生成')
data['story_pack']['video']={'path':str(v),'verification':meta,'query_sha256':hashlib.sha256(a.query.read_bytes()).hexdigest()}
write_chart(data,a.query.with_suffix('.html'))
