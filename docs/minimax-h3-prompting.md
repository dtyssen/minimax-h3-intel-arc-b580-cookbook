# MiniMax H3 — Promptgids voor videogeneratie

> Richtlijn voor het schrijven van prompts voor het MiniMax H3-videomodel
> (Hailuo 3.0) in de ComfyUI H3-stack (poort 8389, workflow `H3-GGUF-T2V`).
>
> **Voor agenten:** wanneer om een H3-videoprompt wordt gevraagd, volg je dit
> document. Belangrijkste randvoorwaarden in onze setup:
>
> - **Eén promptveld** — de workflow heeft alleen een positive prompt
>   (`MiniMaxH3ImageToVideo`-node). Er is **geen apart negatief-promptveld**;
>   negatieve instructies voeg je kort en gericht inline aan het einde toe.
> - **Clipduur** standaard 5 s in onze workflow (instelbaar via
>   `Duration (Seconds)`); het model ondersteunt clips van ±5 tot 15 s.
> - **Native audio** — H3 genereert beeld én geluid in één keer. "Geen geluid
>   beschreven" betekent niet stilte: het model verzint dan zelf een
>   soundtrack. Beschrijf audio dus altijd expliciet.

## Basisformule

Elke prompt leest als een korte productiebrief, niet als een lijst losse
adjectieven:

```
Subject + Actie + Omgeving + Camera + Timing + Visuele stijl + Audio
```

- **Subject** — wie/wat in beeld, met concrete identiteitsdetails (leeftijd,
  kapsel, kleding, accessoires). Niet "een vrouw", maar "een vrouw van ±30 met
  kort zwart haar, een beige trenchcoat en een leren schoudertas".
- **Actie** — animeerbare werkwoorden met richting en tempo: loopt, draait,
  grijpt, kijkt opzij, giet, remt af, schrikt. "Loopt" is zwak; "stapt
  zelfverzekerd op de camera af terwijl haar jas meezwaait" is sterk.
- **Omgeving** — tijd van de dag, weer, locatiedetails. Geef het model een
  complete wereld, geen backdrop.
- **Camera** — shotgrootte, hoek, beweging als pad (zie hieronder).
- **Timing** — wat gebeurt wanneer; bij meerdere shots expliciete timestamps.
- **Stijl** — kies **één** stijl en blijf daarbij.
- **Audio** — ambient, actiegeluiden, muziek en/of dialoog.

Schrijf de prompt **altijd in het Engels** — MiniMax H3 begrijpt Engels
beter dan Nederlands; Nederlandse instructies geven minder voorspelbare
resultaten. De taal van *dialoog* regel je apart met de taaltag (zie Dialoog).

## Structuur van een complete prompt

1. **Scènesequentie** — hoe het begint, zich ontwikkelt en eindigt;
2. **Subject + actie** — wie doet wat, met snelheid en reacties;
3. **Camera** — shotgrootte, hoek, beweging, en waar de beweging op uitdraait;
4. **Geluid** — dialoog, ambient, effecten, muziek;
5. **Eindbeeld** — waarop de shot tot rust komt, wat stabiel moet blijven;
6. **Keep unchanged / avoid** — kort: wat absoluut vast staat en welke
   fouten de oplevering écht raken (het "negatieve veld", zie hieronder).

## Shotgrootte: de belangrijkste beperking

**H3 vervormt personages die ver van de camera staan.** Op afstand zijn er
te weinig pixels voor stabiele ogen, mond en identiteit: gezichten verzachten,
morphen of veranderen van persoon. Upscaling daarna herstelt dat niet.

Praktische regels:

| Situatie | Aanpak |
|---|---|
| Standaard personageshot | **Medium shot** (taille/bovenlichaam) |
| Maximale shotgrootte met leesbaar gezicht | **Medium wide** (knie-shot) |
| Wide/extreme wide | Alleen als gezichtsidentiteit **niet** kritisch is (omgeving, silhouet, massa-scène) of als aparte establishing shot |
| Gezicht op afstand nodig | Plan een aparte detailer/upscale-pass, of herkader dichterbij |

De **moeilijkheidsstapel**: afstand, snelle beweging, occlusie (haar, handen,
voorwerpen), tegenlicht/nacht en profielposten stapelen zich op. Een statisch
frontaal medium-wide shot in daglicht is veilig; een rennend profiel in de
regen 's nachts is niet te redden met alleen een prompt. Vestig de identiteit
eerst in een eenvoudiger versie en voeg daarna **één** moeilijke variabele per
generatie toe.

Tijdens het identiteitskritische moment: gezicht **driekwart naar camera**,
onbelemmerd en gelijkmatig belicht — geen silhouet redden met een prompt.

## Camera

- **Eén camerabeweging per shot** (one-move rule). Meerdere bewegingen willen?
  Splits ze over timestamps/shots.
- Beschrijf beweging als **pad**, met amplitude en snelheid: "the camera pushes
  in with small amplitude at slow speed toward the folded letter" i.p.v. losse
  trefwoorden.
- Beschrijf camera als onderdeel van de actie, en wat er na de beweging zichtbaar
  moet zijn.

Betrouwbare bewegingen: `slow dolly in`, `slow dolly out`, `tracking shot`,
`orbit (360°)`, `crane up/down`, `static shot`, `pan left/right`,
`zoom in/out`. Minder voorspelbaar: `crash zoom`, `dolly zoom`, `whip pan`,
`steadicam follow`, `rack focus`, `bird's eye view`, `dutch angle`.

Framing-woorden om te combineren: `close-up`, `medium close-up`,
`medium shot`, `medium-wide shot`, `over-the-shoulder`, `POV`, `low angle`,
`high angle`.

## Tijdsverloop: timestamps en shotbudget

Voor **één shot** is natuurlijk taal genoeg. Voor **meerdere shots** gebruik je
expliciete timestamps; ranges moeten sequentieel zijn (geen gaten, geen
overlappen), beginnen op `00:00.000` en eindigen op de totale duur:

```
00:00.000–00:03.000 [Shot 1: beschrijving + camera + audio]
00:03.000–00:06.000 [Shot 2: beschrijving + camera + audio]
```

Regels:

- Elk shot **2–5 seconden**; onder ±1,5 s is te kort voor betekenisvolle
  beweging.
- Meer shots = meer risico op inconsistentie tussen cuts.
- Gebruik een **cut** alleen als subject, ruimte of hoek écht verandert; voor
  een strakkere compositie is een push-in schoner dan een extra cut.

Shotbudget per clipduur:

| Duur | Aantal shots | Opmerking |
|---|---|---|
| 4–6 s | 1–2 | Eén doorlopende shot werkt vaak het beste |
| 7–10 s | 2–3 | Sweet spot voor vertellen |
| 11–15 s | 3–5 | Goed plannen; meer drift-risico |

> Onze workflow default is 5 s: houd het bij **1 shot** of maximaal 2.

## Dialoog

H3 synthetiseert spraak natively. Syntax: de tekst staat in een `<d>`-tag met
taaltag, de stembeschrijving erbuiten; spreeksters krijgen stabiele ID's:

```
The young woman with the calm, warm voice (S1) says:
<d>[English] The hardest part isn't the idea. It's the shot.</d>
```

Regels:

- **Kort**: maximaal 1–2 zinnen per shot, passend binnen de clipduur.
- Sprekende personen moeten **dichtbij en frontaal/driekwart** in beeld zijn
  (middenshot of dichterbij) — lip-sync leest alleen dan; dit sluit aan bij de
  shotgrootte-regel hierboven.
- **Voiceover**: schrijf expliciet dat de stem *off-screen* is en dat de
  zichtbare persoon niet meelip-sync't.
- **Tekst in beeld** (borden, neon, labels) schrijf je exact uit:
  `A red neon sign reading "OPEN LATE" glows above the doorway.`
- Elke taal kan in de taaltag, ook `[Dutch]` voor Nederlandse dialoog.

## Audio in drie lagen

Omdat H3 native audio genereert, is een onbeschreven soundtrack een willekeurige
soundtrack. Beschrijf altijd:

1. **Ambient** — de klank van de omgeving: regen, verkeer, kroeggeruis, wind;
2. **Actiegeluiden** — fysieke events in beeld: voetstappen in plassen, glas,
   stof, ademhaling;
3. **Muziek** (non-diegetisch) — instrumentatie, tempo, sfeer en hoe het
   dynamisch meebeweegt met de scène.

Wees specifiek: "soft piano melody, sparse notes" i.p.v. "epic music".
Expliciet "no music, only ambient sounds" is een geldige keuze voor
realisme/documentaire.

## Visuele stijl

- **Één stijl kiezen en vasthouden.** Mengen ("photorealistic anime") verwart
  het model.
- Geen meta-instructies als "4K", "high quality", "best": die beschrijven niets
  wat zichtbaar is. Beschrijf wat je **ziet**: korrel, bokeh, lichtval, kleur.
- Voorbeelden: `photorealistic, shot on 35mm film`, `documentary realism`,
  `cinematic commercial`, `anime`, `film noir`, `retro VHS`.

## Negatieve instructies (zonder negatief veld)

Omdat onze workflow geen negatief-promptveld heeft:

- **Positief formuleren wat vast moet staan** gaat vóór verbieden:
  "the label stays flat and fully readable" > "no warped label".
- Voeg hooguit een **korte** vermeden-lijst toe aan het einde van de prompt,
  alleen fouten die de oplevering écht raken:
  `No facial morphing, no duplicated features, no subtitles, no watermark.`
- Een lange catalogus van alles wat niet mag concurreert met de actie en
  vermindert de kwaliteit. 1 regel, 3–6 items, is genoeg.

## I2V (afbeelding → video)

- Het startbeeld bepaalt uiterlijk, kleding en omgeving: **herbeschrijf de
  bronafbeelding niet**. Besteed de woorden aan beweging, camera en geluid.
- Benoem expliciet wat **stabiel** moet blijven (gezicht, kleding, props).
- In onze setup is I2V de veiligste route voor personageconsistentie: genereer
  eerst een goede startafbeelding (bijv. Krea2, zie `Krea2-T2I.json`) en
  animeer die.

## Personageconsistentie over meerdere shots

- Hergebruik **woord-voor-woord dezelfde** identiteitsbeschrijving in elk shot
  (of gebruik referentie-assets met een expliciete rol: "@1 levert het gezicht").
- Begin met een shot waarin het gezicht leesbaar is (medium of dichterbij)
  **voordat** je naar wide of rugzicht gaat.
- Bij twee personen: geef elk een vaste plek en vaste attributen.
- Verander per generatie maar **één** variabele.

## Snelsjabloon

```
[Shot size + subject with identity details] [does one specific action]
in [environment, time of day, weather]. [One camera move as a path, with
speed/amplitude]. [Visual style: pick one]. [Light description].
[Dialogue: speaker (S1) says: <d>[Language] ...</d>]
[Ambient sounds], [action sounds], [music]. [End frame description].
[Optional: Keep ... unchanged. No ..., no ..., no ...]
```

### Voorbeeld (T2V, 6 s, 1 shot, veilige framing)

```
Medium shot of a woman in her 30s with short black hair and a rust-red coat
standing on a rain-soaked Tokyo street at night. She looks over her shoulder,
then slowly turns three-quarter toward the camera. Static camera, shallow
depth of field. Photorealistic, shot on 35mm film, neon reflections in
puddles, soft frontal key light on her face. She says calmly:
<d>[English] I knew you would follow me.</d>
Rain patters on umbrellas, distant traffic, footsteps in puddles, low
atmospheric synthesizer pad. The shot ends on her face clearly lit under a
neon sign. No facial morphing, no subtitles, no watermark.
```

## Checklist vóór het genereren

- [ ] Prompt **altijd in het Engels** geschreven (ook als dialoog Nederlands is)?
- [ ] Shotgrootte ≤ medium-wide voor elk identiteitskritisch gezicht?
- [ ] Eén duidelijke actie met animeerbare werkwoorden?
- [ ] Maximaal één camerabeweging per shot?
- [ ] Timestamps sequentieel, 2–5 s per shot, eindigend op de totale duur?
- [ ] Dialoog kort, met taaltag, spreker dichtbij in beeld?
- [ ] Audio expliciet: ambient + actie + muziek (of "only ambient")?
- [ ] Één visuele stijl, geen meta-termen?
- [ ] Eindbeeld beschreven (waar dat relevant is)?
- [ ] Vermeldingen-lijst kort (≤ 1 regel) en alleen echte risico's?

## Bronnen (september 2026)

- [JXP — MiniMax H3 Prompt Guide](https://www.jxp.com/minimax/blog/minimax-h3-prompt-guide)
- [inReels — MiniMax H3 Prompt Guide (2026)](https://www.inreels.ai/blog/minimax-h3-prompt-guide)
- [Seedance docs — MiniMax H3 Prompting Guide](https://docs.seedance.tv/en/minimax-h3-prompt-guide)
- [Seedance — Fix Faces at a Distance](https://www.seedance.tv/blog/minimax-h3-fix-faces-at-a-distance)
- [HuggingFace Comfy-Org/MiniMax-H3 #30 — gezichtsvervorming op wide shots](https://huggingface.co/Comfy-Org/MiniMax-H3/discussions/30)
- [Kapwing — How to Prompt MiniMax H3 (Hailuo 3.0)](https://www.kapwing.com/resources/how-to-prompt-minimax-h3-hailuo-3-0-a-guide-for-ai-video-creators/)
- [HackerNoon — MiniMax H3 Prompt Guide](https://hackernoon.com/minimax-h3-prompt-guide-how-to-write-better-hailuo-30-video-prompts)
