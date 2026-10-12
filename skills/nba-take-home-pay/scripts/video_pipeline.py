"""Complete and verify the video belonging to a saved salary query."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parent

def complete_video(output, chart):
    if not output.get('story_pack'):
        return True
    from render_chart import write_chart
    chart = Path(chart).resolve()
    # Never inherit an older video's completion flag.
    output['story_pack'].pop('video', None)
    output['video_delivery'] = {'status': 'pending'}
    write_chart(output, chart)
    stage = 'dependencies'
    try:
        config_path = Path.home()/'.config'/'nba-take-home-pay'/'video.json'
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        environment = os.environ.copy()
        if config.get('node_path') and not environment.get('NODE_PATH'):
            environment['NODE_PATH'] = config['node_path']
        node = os.environ.get('NBA_VIDEO_NODE') or config.get('node') or shutil.which('node')
        ffmpeg = os.environ.get('NBA_VIDEO_FFMPEG') or config.get('ffmpeg') or shutil.which('ffmpeg')
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                pass
        if not node or not ffmpeg:
            raise RuntimeError('视频需要 Node.js、Playwright Chromium 和 FFmpeg；可设置 NBA_VIDEO_NODE / NBA_VIDEO_FFMPEG。')
        def run(command):
            result = subprocess.run(command, capture_output=True, text=True, timeout=900, env=environment)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout)[-3000:])
        with tempfile.TemporaryDirectory(prefix='nba-video-') as temp:
            frames = Path(temp) / 'frames'
            video = Path(temp) / 'video.mp4'
            stage = 'frames'
            run([node, str(SCRIPTS/'export_video_frames.cjs'), output['story_pack']['studio'], str(frames)])
            stage = 'encode_and_verify'
            run([sys.executable, str(SCRIPTS/'encode_video.py'), str(frames), str(video), '--ffmpeg', ffmpeg])
            final = chart.with_suffix('.mp4')
            shutil.copy2(video, final)
            shutil.copy2(video.with_suffix('.verification.json'), final.with_suffix('.verification.json'))
            stage = 'attach'
            run([sys.executable, str(SCRIPTS/'attach_video.py'), str(chart.with_suffix('.json')), str(final)])
        saved = json.loads(chart.with_suffix('.json').read_text())
        output['story_pack'] = saved['story_pack']
        output['video_delivery'] = {'status': 'complete', 'path': str(final)}
        write_chart(output, chart)
        return True
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
        output['story_pack'].pop('video', None)
        output['video_delivery'] = {'status': 'failed', 'stage': stage, 'message': str(error)}
        write_chart(output, chart)
        print('视频未完成（表格和图表已保留）：' + str(error), file=sys.stderr)
        return False

if __name__ == '__main__':
    query = Path(sys.argv[1]).resolve()
    sys.exit(0 if complete_video(json.loads(query.read_text()), query.with_suffix('.html')) else 3)
