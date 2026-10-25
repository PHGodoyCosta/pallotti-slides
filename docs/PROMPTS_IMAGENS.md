# Prompts de imagem — São Vicente Pallotti

As imagens atuais (`src/assets/images/`) são pinturas tradicionais em baixa
resolução (até 751×1024). Para o app precisamos de versões limpas e coerentes
entre si. Use os prompts abaixo num gerador de imagem (Midjourney, DALL·E,
Imagen, Firefly…) e **anexe uma das pinturas atuais como referência de rosto**
(as melhores são `pallotti3.webp` e `pallotti1.webp`).

Traços que precisam se manter em todas: homem de cerca de 50 anos, calvo com
cabelo grisalho nas laterais, rosto magro e sereno, olhar suave para baixo,
batina preta de padre do século XIX com colarinho branco, às vezes capa preta e
crucifixo.

## 1. Ícone do aplicativo (1024×1024, PNG com fundo transparente)

```
Minimalist app icon of Saint Vincent Pallotti, 19th-century Catholic priest,
bald with grey hair on the sides, gentle face, black cassock with white collar,
shown from the shoulders up inside a circular golden halo. Flat vector style,
2–3 tones, clean outlines, deep wine red (#7A1F2B) and warm gold (#C9A24B) on
transparent background, readable at 32px, centered, no text.
```

Variante só com símbolo (para tamanhos pequenos):
```
Minimal flat icon: a simple golden halo over a stylized open book with a small
cross, deep wine red (#7A1F2B) and gold (#C9A24B), transparent background,
geometric, readable at 16px, no text.
```

## 2. Ilustração da tela inicial (1600×900, horizontal)

```
Serene illustration of Saint Vincent Pallotti, 19th-century Roman priest, bald
with grey side hair, kind thoughtful expression, black cassock and cape,
holding a small crucifix, standing on the right third of the frame, soft warm
light from the left, subtle background of a Roman church interior blurred into
warm gold tones. Modern painterly style inspired by classical Catholic
iconography, clean and calm, generous empty space on the left for interface
text, muted palette of wine red, gold and cream.
```

## 3. Retrato para a página "Sobre" (1200×1500, vertical)

```
Respectful high-resolution restoration of a classical oil portrait of Saint
Vincent Pallotti: bald 19th-century priest with grey side hair, gentle downward
gaze, black cassock with white collar, golden halo, dark warm background.
Preserve the likeness of the reference painting, sharpen details, remove
cracks and noise, natural skin tones, museum-quality lighting, no added
objects, no text.
```

## 4. Tela de abertura / splash (1200×700)

```
Elegant splash screen artwork: silhouette of Saint Vincent Pallotti in profile
(bald, cassock and cape) in deep wine red, framed by a thin golden circular
halo, on a soft cream background with a faint pattern of rays. Minimal,
balanced, large empty area at the bottom for the title "Pallotti Slides", no
text in the image.
```

## 5. Estado vazio (ex.: "nenhuma missa ainda") (800×600, fundo transparente)

```
Small friendly flat illustration: an open hymn book with musical notes and a
small golden halo floating above it, wine red and gold line art, transparent
background, simple and light, no text.
```

## Dicas

- Gere em resolução alta e reduza depois. Para o ícone, exporte também 256,
  128, 64, 48, 32 e 16 px (e `.ico` no Windows).
- Peça 4 variações e escolha mantendo a **mesma paleta** em todas.
- Se o gerador deformar o rosto, use a opção de referência de imagem (image
  prompt / character reference) com peso alto.
- Coloque os arquivos finais em `src/pallotti_slides/resources/images/` (depois
  do M0) com nomes descritivos: `icone.png`, `inicio.png`, `sobre.png`,
  `splash.png`, `vazio.png`.
