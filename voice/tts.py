"""ElevenLabs v3 orqali ovoz yaratadi. Ishlatish:
   export ELEVENLABS_API_KEY=...   (yangi kalit)
   python3 tts.py                  (voice_id ixtiyoriy: python3 tts.py <voice_id>)
"""
import os, sys, json, urllib.request

key = os.environ["ELEVENLABS_API_KEY"]
voice = sys.argv[1] if len(sys.argv) > 1 else "pNInz6obpgDQGcFmaJgB"  # Adam: past, dag'al diktor ovozi
text = open(os.path.join(os.path.dirname(__file__), "nokia_tagged.txt"), encoding="utf-8").read()

body = json.dumps({
    "text": text,
    "model_id": "eleven_v3",
    "language_code": "uz",
    "voice_settings": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.5, "use_speaker_boost": True},
}).encode()
req = urllib.request.Request(
    f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_192",
    data=body, headers={"xi-api-key": key, "Content-Type": "application/json"})
out = os.path.join(os.path.dirname(__file__), "nokia_voice.mp3")
with urllib.request.urlopen(req) as r, open(out, "wb") as f:
    f.write(r.read())
print("tayyor:", out)
