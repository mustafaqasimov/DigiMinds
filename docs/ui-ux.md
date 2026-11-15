# Map workspace redesign — 15 November 2026

The citizen and dispatcher screens now share a map workspace instead of a vertically stacked dashboard. All code and icons are original to this project; no Perimeter or Watch Duty brand assets are included.

## Reference patterns

- [Perimeter Map](https://perimeterplatform.com/perimeter-map): a common map for closures, resources and zones, a compact information sidebar, and map-layer controls. Its public map shell was inspected; the basemap did not render in this browser.
- [Watch Duty](https://www.watchduty.org/): clear hazard symbols, a consolidated alert feed and concise shelter/evacuation information. The official site's illustrated interface was inspected. The live web app reported that this browser was unsupported, so its live interactions were not evaluated.

## Implemented behavior

- Citizen: recommended walking route, occupancy bars, shelter search and details, a prominent SOS entry point with four one-click emergency choices, safe status and a visible unsent queue.
- Dispatcher: active critical alert first, incident/type filters, shelter/team tabs, compact map metrics and contextual response actions. Expired alert triggers use a neutral archived style.
- Road editing is an explicit mode. Selecting a road opens details; a separate button applies closure/reopening. This avoids mutating routes during ordinary map navigation.
- Layers can independently hide shelters, incidents, teams and zone overlays. Drag, wheel zoom, zoom/reset controls and keyboard map navigation use bundled SVG geometry.
- Map markers show active incidents by default; selecting a historical incident displays that incident without crowding the default map.
- Role and scenario tools are separate dialogs; mobile users can reach them through the account menu. Backend permission checks remain authoritative.
- UI text is available in Azerbaijani, English and Russian. Place names remain the dataset's proper names. Icon-only controls retain accessible names. Dialog focus is contained and Escape closes overlays. Form drafts and scrolling survive snapshot renders; drafts are scoped to the selected shelter.
- The Service Worker precaches the new UI, map and translation modules. There are no remote font, map-tile or frontend-script dependencies.

## Validation

- 33 Python tests and 8 Node tests pass. New UI regression tests cover public/operational separation, active versus archived alerts, explicit road mutation, escaped search input, translation parity and offline module coverage.
- Browser: citizen fire SOS accepted; repeat support kept report count at one; safe status updated; shelter search narrowed to the northern stadium; live occupancy changed from 384 to 385 and was restored to 384; layers toggled without discarding the in-progress occupancy input; road selection left the road open, closure changed its status to closed, and reopening restored it.
- Stopped the managed backend and reloaded the citizen app: the cached redesigned interface and SVG map opened, the offline banner was visible, and browser routing returned the 872 m / 11.6 min path. Restarted the backend after the check.
- Responsive CSS inspected using browser zoom at 545 and 337 CSS-pixel widths, with no horizontal document overflow. This is a narrow-viewport browser check, not a physical-device audit. A tablet grid-column bug and missing labels on mobile icon controls were corrected during this pass.

The basemap and operational data are still synthetic training data, visibly labelled in the interface. This redesign does not make the prototype official evacuation guidance.
