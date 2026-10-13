"""Test the frozen executable's renderer and optional draft resources."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exe', type=Path)
    args = parser.parse_args()
    exe = args.exe.resolve()
    with tempfile.TemporaryDirectory(prefix='auto-edit-') as directory:
        root = Path(directory)
        source = root / 'sample.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
            'color=red:s=64x64:r=30:d=4', '-vf', "drawbox=color=blue:t=fill:enable='gte(t,2)*lt(t,3)'",
            '-c:v', 'libx264', '-g', '120', str(source)], check=True)
        plan = root / 'plan.json'
        plan.write_text(json.dumps({'clips':[{'file':'sample.mp4','start':2,'end':3,
            'speed':1.2,'output_duration':2,'loop':True,'title':'Action'}]}), encoding='utf-8')
        subprocess.run([str(exe), '--input', str(root), '--plan', str(plan), '--output', str(root/'out.mp4'),
            '--work', str(root/'work'), '--width', '64', '--height', '64', '--mute-source',
            '--draft', str(root/'editable')], check=True)
        stream = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v',
            '-show_entries', 'stream=nb_frames,duration', '-of', 'json', str(root/'out.mp4')]))['streams'][0]
        assert int(stream['nb_frames']) == 60, stream
        data = json.loads((root/'editable/draft_content.json').read_text(encoding='utf-8'))
        assert data['duration'] == 2_000_000
        assert (root/'editable/install_draft.py').is_file()
        assert (root/'editable/assets/action_01.mp4').is_file()
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=300:duration=3.4', str(root/'voice.wav')], check=True)
        (root/'voice.srt').write_text('1\n00:00:00,200 --> 00:00:02,800\nAI\n', encoding='utf-8')
        plan.write_text(json.dumps({
            'clips': [{'file':'sample.mp4','start':2,'end':3,'filter':'mono','effects':['zoom_in']},
                      {'file':'sample.mp4','start':2,'end':3}],
            'narration': {'audio':'voice.wav','subtitles':'voice.srt'},
            'transition': {'name':'fade','duration':.2},
            'elements': [{'type':'icon','name':'check','start':.1,'end':.9,'size':.3,'x':.1,'y':.1}],
            'sound_effects': [{'name':'ding','start':1}]
        }), encoding='utf-8')
        subprocess.run([str(exe), '--input', str(root), '--plan', str(plan), '--output', str(root/'rich.mp4'),
            '--work', str(root/'work'), '--width', '64', '--height', '64', '--mute-source',
            '--music', str(root/'voice.wav'), '--draft', str(root/'rich-draft')], check=True)
        data = json.loads((root/'rich-draft/draft_content.json').read_text(encoding='utf-8'))
        assert data['duration'] == 3_400_000
        assert len(data['tracks']) == 5
        stream = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v',
            '-show_entries', 'stream=nb_frames', '-of', 'json', str(root/'rich.mp4')]))['streams'][0]
        assert int(stream['nb_frames']) == 102, stream
        print('Frozen smoke passed: native draft/60 frames; enhanced draft/5 tracks/102 frames; bundled installer.')


if __name__ == '__main__':
    main()
