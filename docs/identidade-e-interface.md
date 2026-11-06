# Nexo Radar — identidade e interface

O produto tem marca própria, independente das empresas atendidas. A identidade usa azul profundo `#0D1930`, azul `#286BED`, ciano `#42E8E0` e violeta `#8362FF`.

## Arquivos da marca

- `web/public/brand/nexo-logo.svg`: assinatura vetorial.
- `web/public/brand/nexo-symbol.svg`: símbolo vetorial e favicon.
- `web/public/brand/nexo-symbol-reference.png`: referência rasterizada do vetor.
- `web/public/brand/nexo-symbol-3d.png`: renderização 3D com transparência, aplicada no login.

A versão 3D foi gerada com a ferramenta integrada ImageGen, usando a referência vetorial rasterizada. O vetor permanece como fonte da marca e alternativa de carregamento.

Prompt final utilizado:

> Use case: logo-brand / precise-object-edit. Create a premium photorealistic 3D material rendition of the provided Nexo Radar logo icon, for an enterprise SaaS login screen. Preserve the logo's exact identity: navy rounded square tile; geometric capital N made of two straight vertical stems joined by a thick diagonal, with cyan-to-blue-to-violet gradient; one separate cyan circular signal dot at the upper right. Keep the exact geometry, proportions, one N and one dot. Render the entire icon as a thick, softly beveled midnight-blue anodized metal and dark glass tile, with the N as polished luminous cyan/blue/violet glass inset and the small dot as a glossy cyan inlay. Tasteful high-end product photography, restrained optical reflections, crisp details, delicate cyan rim light left and violet rim light right. Mild three-quarter view, rotated only slightly, very legible N facing viewer. Centered isolated floating icon, generous transparent margin, icon occupies 75% of square canvas. Genuinely transparent alpha background: no backdrop, no ground plane, no scene, no black rectangle outside the icon, no checkerboard, no text or extra symbols. Elegant corporate tech aesthetic, sophisticated rather than flashy. This is a material and dimensional transformation of the reference logo; do not redesign the mark.

## Componentes e movimento

`BlurText` e `SpotlightCard` foram importados do projeto oficial [React Bits](https://github.com/DavidHDev/react-bits). A licença e o manifesto com origem e hashes ficam em `web/src/components/reactbits/`. O uso é integrado ao aplicativo, sem redistribuir uma biblioteca de componentes.

Motion controla as transições curtas de entrada e dos indicadores. O sistema respeita `prefers-reduced-motion`, mantém o menu operável por teclado e usa rótulos acessíveis nos campos. O layout do login muda de duas colunas para um cabeçalho compacto em telas menores. O painel mantém seus filtros, listas, detalhes e avaliações responsivos.

## Acesso

O login principal usa e-mail e senha, verificados pelo Supabase. Senhas não são armazenadas no banco da aplicação. Sessões usam cookies HttpOnly, Secure e SameSite=Strict. Convites de primeiro acesso expiram em 24 horas e só podem ser usados uma vez.

O painel público mostra apenas informações públicas de licitações. As avaliações e os exemplos da equipe exigem autenticação no servidor. A senha de app do Gmail é uma configuração exclusiva do servidor e nunca faz parte do frontend.
