# Fleet prototype imagery

Generated with the built-in `imagegen` tool for this UI mockup. These are
fictional vehicle product images, not photographs of Grupo Lorena's fleet.

- `refrigerated-truck.png`: white compact cab-over refrigerated distribution
  truck, three-quarter front left view, entire vehicle and wheels visible;
  neutral automotive catalog lighting, transparent background, no text or logos.
  A subsequent background-extraction edit removed the studio glow while
  preserving the complete truck.
- `cargo-van.png`: white commercial cargo delivery van, three-quarter front
  left view, entire vehicle visible; matching neutral catalog lighting,
  transparent background, no people, text, scenery, logos, or watermark.

All assets are local so the prototype does not depend on third-party image URLs.

## Prompt set (built-in tool)

Both generation prompts used this shared specification, replacing `{subject}`:

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Subject: {subject}. Composition: a single vehicle centered horizontally occupying 85 percent of a wide landscape frame, ample transparent breathing room on all four sides, wheels fully visible, camera at wheel-to-headlight height, mild perspective, consistent with premium automotive product catalog photography. Studio soft neutral lighting. Pure white paint, charcoal glass and tires, natural subtle ambient shadow immediately under the tires only. Real transparent alpha background. No people, no text, no logos, no license plate text, no scenery, no ground plane, no watermark. Crisp fine details, polished realistic vehicle asset for a professional logistics dashboard, not an illustration. One vehicle only.

Truck subject:

> a compact white cab-over refrigerated box delivery truck, three-quarter front left side view, entire vehicle visible, cab on left, white insulated cargo box on right, black tires, realistic silver details, sized like a 5-ton bakery distribution vehicle

Van subject:

> a clean white commercial cargo delivery van, three-quarter front left side view, entire vehicle visible, front facing left, no windows on cargo panels, black tires, realistic silver details

Final truck background-extraction edit:

> Edit target: the attached white refrigerated truck product photo. Remove the entire gray glow, studio backdrop and all background behind and around the vehicle, replace with true transparent alpha. Keep only the complete truck with all wheels, mirrors, cargo body exactly unchanged. No gray rectangle, no gray vignette, no atmospheric glow, no ground plane. A faint short contact shadow immediately beneath tires is acceptable, everything else must be fully transparent. Preserve photorealistic truck details and framing.

## Additional vehicle types

Generated with the built-in `imagegen` tool, using the two original local images
as style references. All assets retain a transparent alpha background.

### `pickup.png`

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Input images are style references only: match white body paint, soft neutral studio lighting, realistic finish and front-left three-quarter camera angle with vehicle nose pointing left. Generate a distinct new vehicle as described. Composition: one whole vehicle centered in a wide landscape frame occupying 85 percent width, ample transparent breathing room, wheels fully visible, camera at headlight height, mild perspective. Pure white paint, charcoal glass and tires, natural subtle contact shadow immediately under tires only. Real transparent alpha background. No people, no text, no logos, no readable plates, no scenery, no ground plane, no watermark. Crisp realistic professional automotive catalog photography. One vehicle only. Subject: a white diesel double-cab midsize commercial pickup truck with an empty open cargo bed, stock road wheels, no off-road accessories

### `dry-box-truck.png`

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Input images are style references only: match white body paint, soft neutral studio lighting, realistic finish and front-left three-quarter camera angle with vehicle nose pointing left. Generate a distinct new vehicle as described. Composition: one whole vehicle centered in a wide landscape frame occupying 85 percent width, ample transparent breathing room, wheels fully visible, camera at headlight height, mild perspective. Pure white paint, charcoal glass and tires, natural subtle contact shadow immediately under tires only. Real transparent alpha background. No people, no text, no logos, no readable plates, no scenery, no ground plane, no watermark. Crisp realistic professional automotive catalog photography. One vehicle only. Subject: a white medium duty cab-over dry freight box truck, plain enclosed rectangular cargo box WITHOUT a refrigeration unit, two axles

### `flatbed-truck.png`

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Input images are style references only: match white body paint, soft neutral studio lighting, realistic finish and front-left three-quarter camera angle with vehicle nose pointing left. Generate a distinct new vehicle as described. Composition: one whole vehicle centered in a wide landscape frame occupying 85 percent width, ample transparent breathing room, wheels fully visible, camera at headlight height, mild perspective. Pure white paint, charcoal glass and tires, natural subtle contact shadow immediately under tires only. Real transparent alpha background. No people, no text, no logos, no readable plates, no scenery, no ground plane, no watermark. Crisp realistic professional automotive catalog photography. One vehicle only. Subject: a white medium duty cab-over flatbed truck, empty open low steel cargo platform with NO box and NO high side rails, two axles

## Extended catalog: four additional body types

Generated with the built-in `imagegen` tool using local catalog images as style
references. These are fictional product cutouts for the UI prototype. The panel
van uses the final compact-body variant; the initial draft was not shipped.

### `compact-panel-van.png`

> Use case: product-mockup. Generate a NEW vehicle catalog cutout. The reference image is ONLY a reference for white paint, front-left camera direction and studio lighting; do not copy its vehicle body. Subject: a SMALL COMPACT low-roof two-seat urban panel delivery van with the unmistakable short boxy proportions of a Volkswagen Caddy Cargo. Short wheelbase, roof barely above the windshield, small 15 inch stock steel wheels, upright squared off rear body, short low horizontal hood, simple narrow horizontal headlights and rectangular grille, windowless rear cargo panels. Much smaller than a Ford Transit; NOT a full-size or mid-size Transit or Sprinter. Pure white body, black bumper trim, no logos or readable text. One complete vehicle nose pointing left, realistic automotive catalog photo, three-quarter front-left side angle, mild perspective, entire wheels mirrors and body visible centered with transparent breathing room. Soft neutral studio lighting, dark glass, subtle contact shadow only under tires. True transparent alpha background, no backdrop, no ground plane, no gray glow, no people, no text, no watermark.

### `curtain-side-truck.png`

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Input images are style references only: match white body paint, soft neutral studio lighting, realistic finish and front-left three-quarter camera angle with vehicle nose pointing left. Generate a distinct new vehicle as described. Composition: one whole vehicle centered in a wide landscape frame occupying 85 percent width, generous transparent breathing room, all wheels and mirrors fully visible, camera at headlight height, mild perspective, more side visible than front. Pure white paint, charcoal glass and tires, natural subtle contact shadow immediately under tires only. True transparent alpha background. No gray glow, no atmospheric backdrop, no ground plane. No people, no text, no logos, no readable plates, no scenery, no watermark. Crisp realistic professional automotive catalog photography. One vehicle only. Subject: a white medium-duty cab-over two-axle curtain-sided cargo truck, closed pale white fabric tarpaulin cargo body with clearly visible vertical buckles and lower curtain straps, no refrigeration equipment

### `semi-trailer-truck.png`

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Input images are style references only: match white body paint, soft neutral studio lighting, realistic finish and front-left three-quarter camera angle with vehicle nose pointing left. Generate a distinct new vehicle as described. Composition: one whole vehicle centered in a wide landscape frame occupying 85 percent width, generous transparent breathing room, all wheels and mirrors fully visible, camera at headlight height, mild perspective, more side visible than front. Pure white paint, charcoal glass and tires, natural subtle contact shadow immediately under tires only. True transparent alpha background. No gray glow, no atmospheric backdrop, no ground plane. No people, no text, no logos, no readable plates, no scenery, no watermark. Crisp realistic professional automotive catalog photography. One vehicle only. Subject: a white heavy semi truck with a white cab-over tractor and attached long plain enclosed white box semi-trailer, articulated vehicle, three tractor axles and two trailer axles, all fully visible, no refrigeration equipment

### `tanker-truck.png`

> Use case: product-mockup. Asset type: photorealistic fleet management UI vehicle cutout. Input images are style references only: match white body paint, soft neutral studio lighting, realistic finish and front-left three-quarter camera angle with vehicle nose pointing left. Generate a distinct new vehicle as described. Composition: one whole vehicle centered in a wide landscape frame occupying 85 percent width, generous transparent breathing room, all wheels and mirrors fully visible, camera at headlight height, mild perspective, more side visible than front. Pure white paint, charcoal glass and tires, natural subtle contact shadow immediately under tires only. True transparent alpha background. No gray glow, no atmospheric backdrop, no ground plane. No people, no text, no logos, no readable plates, no scenery, no watermark. Crisp realistic professional automotive catalog photography. One vehicle only. Subject: a white medium-heavy rigid three-axle liquid tanker truck, white cab-over cab and a smooth white cylindrical food-grade liquid tank with subtle silver fittings and a ladder, no hazard symbols


