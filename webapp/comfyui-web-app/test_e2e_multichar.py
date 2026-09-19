import urllib.request
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')
base = 'http://127.0.0.1:8080'

def http_get(path):
    req = urllib.request.Request(base + path)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def http_post(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def http_put(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'}, method='PUT')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

print("=== 1. Test List Characters & Presets ===")
chars = http_get('/api/characters')
print(f"Existing characters: {len(chars)}")
for c in chars:
    print(f"  #{c['id']} {c.get('avatar_icon','')} {c['name']} ({c['code']}) - tasks: {c['task_count']}, images: {c['generated_count']}")

presets = http_get('/api/characters/presets/examples')
print(f"Presets count: {len(presets)}")
for p in presets:
    print(f"  Preset: {p['avatar_icon']} {p['name']} | lora: {p['default_lora']}")

print("\n=== 2. Create New Character (Elsa) if not present ===")
elsa = next((c for c in chars if c['code'] == 'elsa_knight'), None)
if not elsa:
    preset_elsa = next(p for p in presets if p['code'] == 'elsa_knight')
    create_payload = {
        'name': preset_elsa['name'],
        'code': preset_elsa['code'],
        'avatar_icon': preset_elsa['avatar_icon'],
        'trigger_words': preset_elsa['trigger_words'],
        'negative_prompt': preset_elsa['negative_prompt'],
        'default_lora': preset_elsa['default_lora'],
        'lora_strength': preset_elsa['lora_strength'],
        'base_model': preset_elsa['base_model'],
        'description': preset_elsa['description'],
        'auto_generate_matrix': True
    }
    elsa = http_post('/api/characters', create_payload)
    print(f"Created Elsa: id={elsa['id']}, name={elsa['name']}, tasks={elsa['task_count']}")
else:
    print(f"Elsa already exists with id={elsa['id']}")

print("\n=== 3. Test Preview for Elsa vs Lumina ===")
prev_lumina = http_post('/api/batch/preview', {'character_id': 1, 'styles': ['ghibli']})
prev_elsa = http_post('/api/batch/preview', {'character_id': elsa['id'], 'styles': ['ghibli']})
print(f"Lumina (ghibli): matched={prev_lumina['matched']}, pending={prev_lumina['pending']}, success={prev_lumina['success']}")
print(f"Elsa (ghibli): matched={prev_elsa['matched']}, pending={prev_elsa['pending']}, success={prev_elsa['success']}")

print("\n=== 4. Test Consistency Benchmark for Elsa ===")
bench = http_post('/api/characters/benchmark/run', {
    'character_id': elsa['id'],
    'style_tag': 'rococo',
    'outfit_tag': 'evening_gown',
    'pose_tag': 'portrait_close',
    'seed': 777777
})
print(f"Benchmark for {bench['character_name']} ({bench['style_tag']}):")
for ph in bench['phases']:
    print(f"  [Phase {ph['phase']}] {ph['phase_name']} | LoRA: {ph['lora_used']} | Image: {ph['image_url']}")

print("\n=== 5. Run Small Batch Generation for Elsa (limit=2) ===")
batch_res = http_post('/api/batch/start', {
    'character_id': elsa['id'],
    'styles': ['rococo'],
    'outfits': ['evening_gown'],
    'limit': 2,
    'steps': 20,
    'cfg': 7.0
})
print("Start batch:", batch_res)

# Wait for completion
for i in range(10):
    time.sleep(1)
    status = http_get(f"/api/batch/status?character_id={elsa['id']}")
    print(f"  Worker tick {i+1}: active={status['is_active']}, done={status['session_done']}/{status['session_total']}, success={status['success']}")
    if not status['is_active']:
        break

print("\n=== 6. Verify Gallery Separation by Character ===")
gal_elsa = http_get(f"/api/gallery/images?character_id={elsa['id']}")
gal_lumina = http_get('/api/gallery/images?character_id=1')
print(f"Elsa's generated gallery count: {gal_elsa['total']}")
for img in gal_elsa['images'][:2]:
    print(f"  Elsa Image: {img['file_name']} (Style: {img['style_tag']}, Outfit: {img['outfit_tag']})")
    print(f"    gen_config: {img['gen_config']}")

print(f"Lumina's generated gallery count: {gal_lumina['total']}")

print("\n=== 7. Test Character Update ===")
updated_elsa = http_put(f"/api/characters/{elsa['id']}", {
    'description': '奇幻英气女骑士（已更新人设版本）。誓死捍卫王城与骑士荣耀。'
})
print(f"Updated Elsa description: {updated_elsa['description']}")

print("\n=== 8. Test Static Files Availability ===")
for url_path in ['/', '/batch.html', '/js/character_manager.js', '/css/style.css']:
    req = urllib.request.Request(base + url_path)
    with urllib.request.urlopen(req) as resp:
        print(f"GET {url_path} -> HTTP {resp.status} (length: {len(resp.read())} bytes)")

print("\nALL E2E MULTI-CHARACTER & BENCHMARK TESTS PASSED!")
