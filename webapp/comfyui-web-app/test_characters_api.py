import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
base = 'http://127.0.0.1:8080'

# 1. List characters
with urllib.request.urlopen(base + '/api/characters') as resp:
    chars = json.loads(resp.read().decode('utf-8'))
    print('1. Characters count:', len(chars))
    print('   First char:', chars[0]['name'], chars[0]['code'], chars[0]['avatar_icon'], 'tasks:', chars[0]['task_count'], 'images:', chars[0]['generated_count'])

# 2. Get presets
with urllib.request.urlopen(base + '/api/characters/presets/examples') as resp:
    presets = json.loads(resp.read().decode('utf-8'))
    print('2. Presets count:', len(presets))
    for p in presets:
        print('   - Preset:', p['name'], p['code'], p['avatar_icon'])

# 3. Create a new character (Hoshino) if not already created
created_id = None
for c in chars:
    if c['code'] == 'hoshino_chan':
        created_id = c['id']
        print('   Character hoshino_chan already exists with id:', created_id)

if not created_id:
    new_char_payload = {
        'name': '星野 (Hoshino)',
        'code': 'hoshino_chan',
        'avatar_icon': '🌸',
        'trigger_words': '1girl, (hoshino_face:1.25), (soft pastel pink hair:1.2), (golden yellow halo:1.15), ahoge, (blue and amber heterochromia:1.2), sleepy half-closed eyes',
        'negative_prompt': 'silver hair, black hair, green eyes, missing halo, bad anatomy',
        'default_lora': 'hoshino_sdxl_v1.safetensors',
        'lora_strength': 0.85,
        'base_model': 'sdxl',
        'description': '学院慵懒风粉发光环少女。左蓝右金异色瞳与略带困意的温柔眼神。',
        'auto_generate_matrix': True
    }
    req = urllib.request.Request(base + '/api/characters', data=json.dumps(new_char_payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        created = json.loads(resp.read().decode('utf-8'))
        created_id = created['id']
        print('3. Created character:', created_id, created['name'], 'tasks:', created['task_count'])

# 4. List characters again
with urllib.request.urlopen(base + '/api/characters') as resp:
    chars2 = json.loads(resp.read().decode('utf-8'))
    print('4. New characters count:', len(chars2))
    for c in chars2:
        print(f"   #{c['id']} {c['avatar_icon']} {c['name']} ({c['code']}) - tasks: {c['task_count']}, images: {c['generated_count']}")

# 5. Test Consistency Benchmark endpoint
bench_payload = {
    'character_id': created_id,
    'style_tag': 'cyberpunk',
    'outfit_tag': 'school_uniform',
    'pose_tag': 'portrait_close',
    'seed': 99999
}
req = urllib.request.Request(base + '/api/characters/benchmark/run', data=json.dumps(bench_payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    bench = json.loads(resp.read().decode('utf-8'))
    print('5. Benchmark response:', bench['character_name'], bench['style_tag'])
    for ph in bench['phases']:
        print(f"   Phase {ph['phase']}: {ph['phase_name']} (LoRA: {ph['lora_used']})")
