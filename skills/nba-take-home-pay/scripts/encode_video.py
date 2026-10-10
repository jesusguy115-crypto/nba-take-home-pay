"""Encode ordered 16:9 PNG scenes as deterministic 30fps H.264 video.
Usage: python encode_video.py /path/to/frames output.mp4 --ffmpeg /path/to/ffmpeg
Requires ffmpeg with libx264; inputs are numbered PNGs exported from studio SVGs.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import json
import re

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--seconds',type=float,default=6,help='每幕秒数，默认6秒，须大于1')
    p.add_argument('--ffmpeg',default=shutil.which('ffmpeg'))
    args=p.parse_args()
    if not args.ffmpeg:p.error('需要FFmpeg；不能用实时录屏冒充离线稳定导出')
    if args.seconds<=1:p.error('每幕须大于1秒')
    frames=sorted(args.frames.glob('*.png'))
    if not frames:p.error('没有PNG分幕文件')
    command=[args.ffmpeg,'-y','-hide_banner','-loglevel','warning']
    for f in frames:command+=['-loop','1','-framerate','30','-t',str(args.seconds), '-i',str(f)]
    filters=[f'[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x101416,setsar=1,format=yuv420p,settb=AVTB[v{i}]' for i in range(len(frames))]
    last='v0'
    for i in range(1,len(frames)):
        name=f'x{i}';filters.append(f'[{last}][v{i}]xfade=transition=fade:duration=0.4:offset={i*(args.seconds-.4):.1f}[{name}]');last=name
    args.output.parent.mkdir(parents=True,exist_ok=True)
    command+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map',f'[{last}]','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r','30','-fps_mode','cfr','-movflags','+faststart',str(args.output)]
    subprocess.run(command,check=True)
    verification=subprocess.run([args.ffmpeg,'-hide_banner','-i',str(args.output),'-vf','vfrdet','-f','null','-'],capture_output=True,text=True,check=True)
    if 'VFR:0.000000' not in verification.stderr:
        raise ValueError('视频固定帧率验证未通过')
    args.output.with_suffix('.verification.json').write_text(json.dumps({'status':'verified','resolution':'1920x1080','fps':30,'codec':'H.264','audio':False,'scenes':len(frames),'seconds_per_scene':args.seconds,'cfr_verified':True,'frame_manifest':json.loads((args.frames/'manifest.json').read_text()) if (args.frames/'manifest.json').exists() else None},indent=2))
    print(f'{args.output}: 1920x1080, 30 fps CFR, {args.seconds+(len(frames)-1)*(args.seconds-.4):.1f}s, silent H.264')
if __name__=='__main__':main()
