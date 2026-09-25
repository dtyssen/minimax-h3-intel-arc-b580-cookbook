# H3-GGUF-T2V-RTX-test — test-workflow (Reddit "Singularity" optimalisatie)

Gebaseerd op r/comfyui post "H3 Singularity but 40 faster and better quality".

## Aanpassingen t.o.v. H3-GGUF-T2V.json

- **Resolutie:** 0,5 MP (960×544) in plaats van 0,4 MP (1344×768) — gebruiker vond 0,5 MP de sweet spot.
- **Stappen:** 8 (baseline), gebruiker noemt 8 en 12 als optimaal.
- **Scheduler:** simple, CFG 1.0 (ongewijzigd).
- **LoRA:** r34l1sm.safetensors op 1.0 ("full blast"). De turbo-LoRA is vervangen; combineer indien nodig beide via twee LoraLoaderModelOnly-nodes.
- **Easy Cache:** al uitgeschakeld (`false`, geen links) — gebruiker meldt geen snelheidswinst en risico op degradatie.
- **Stap 2 (RTX polishing):** nog niet geïmplementeerd — RTX-node ontbreekt in de repo. De gebruiker beschrijft "drop in RTX right before the Video is saved in Step 2" als extra polishing/upscale-stap. Voeg een `ImageResizeKJv2` (2× lanczos, 1920×1080) of exacte RTX-node in vóór de `SaveVideo`.

## Gebruik

1. Zorg dat `r34l1sm.safetensors` in `models/loras/` staat.
2. Laad workflow op H3-stack (poort 8389).
3. Test op 0,5 MP (960×544) met 8 stappen.
4. Vergelijk tegen `H3-GGUF-T2V.json` (0,4 MP, turbo LoRA) voor snelheid/kwaliteit.

## Ontbrekende onderdelen

- **RTX-node:** exacte ComfyUI-node voor "RTX" polishing niet gevonden. De gebruiker verwijst mogelijk naar een custom node of een specifieke upscaler (bijv. RTX Video Super Resolution, of een aangepaste workflow-stap). Test met `ImageResizeKJv2` (2×, lanczos) als proxy.
- **ProRes 4444 / 12-bit HDR:** onze workflow output MP4; gebruiker test in DaVinci met ProRes 4444. Niet toepasbaar zonder workflow-aanpassing.
- **0,3 MP / 0,4 MP varianten:** gebruiker testte uitgebreid 0,3–0,5 MP. Onze benchmark gebruikt 0,4 MP als minimum.
