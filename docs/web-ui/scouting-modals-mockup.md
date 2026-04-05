# Scouting UI — ASCII mockups (modals)

Reference layout for the Scouting pipeline: kanban stays in-page; **Details** and **Open Feasibility** open large centered modals over a dimmed backdrop.

---

## 1. Scouting mode (main canvas)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Sidebar …                    │  Scouting Pipeline                            │
│                               │  Track sites through evaluation stages…       │
│                               │  [ Brownfield ] [ Greenfield ] [ BESS ]       │
│                               │                                                │
│                               │  ┌─────────┐ ┌─────────┐ ┌─────────┐ …       │
│                               │  │Identified│ │ Screened │ │ Scored  │         │
│                               │  │─────────│ │─────────│ │─────────│         │
│                               │  │ [card]  │ │ [card]  │ │ [card]  │         │
│                               │  │Details  │ │Details  │ │Details  │         │
│                               │  │Feasib.  │ │Feasib.  │ │Feasib.  │         │
│                               │  └─────────┘ └─────────┘ └─────────┘         │
│                               │                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

No detail strip under the board — overlays only when the user asks.

---

## 2. Site detail modal (`Details`)

Backdrop: semi-transparent + blur. Content: **modal-large** (~96vw max 1200px), scrollable body.

```
                    ┌────────────────────────────────────────────────────────┐
                    │  Karoo Solar East                           [ × close ] │
                    ├────────────────────────────────────────────────────────┤
                    │  Technology: solar                                   │
                    │  Country: ZA                                         │
                    │  Location: -32.1, 22.4                               │
                    │  Pipeline stage: screened                            │
                    │  …                                                    │
                    │                                                       │
                    │  Team notes                                           │
                    │  ┌──────────────────────────────────────────────────┐ │
                    │  │ Contacts: … next call … grid queue …             │ │
                    │  │                                                   │ │
                    │  │                                                   │ │
                    │  └──────────────────────────────────────────────────┘ │
                    │  [ Save notes ]  [ Show on Discovery map ]            │
                    └────────────────────────────────────────────────────────┘
```

- Click outside (backdrop) or **Esc** closes.
- Title line = `h2.modal-title` (site name).

---

## 3. Feasibility modal (`Open Feasibility`)

Same shell size; header shows study title + progress badge.

```
                    ┌────────────────────────────────────────────────────────┐
                    │  Feasibility Study              [ 2/5 done ]  [ × close ]│
                    ├────────────────────────────────────────────────────────┤
                    │  [ Production ] [ Trading ] [ Grid ] [ Regulatory ] …   │
                    │  ─────────────────────────────────────────────────────  │
                    │                                                       │
                    │   (tab content: run / re-run, findings, badges, chart) │
                    │                                                       │
                    │                                                       │
                    └────────────────────────────────────────────────────────┘
```

---

## 4. Stacking (conceptual)

```
     User on Scouting
            │
            ├─► Details        ──►  detail modal (z-index modal layer)
            │
            └─► Open Feasibility ──►  feasibility modal (same layer; only one
                                      typically open at a time)
```

---

## 5. Implementation pointers

| Mockup region | DOM id (approx.)        | Notes                          |
|---------------|-------------------------|--------------------------------|
| Detail shell  | `#scoutingDetailModal`  | `.modal` + `.modal-large`      |
| Feasibility   | `#feasibilityModal`     | `#feasibilityTabs`, `#feasibilityContent` |

CSS: `.modal-large` in `ui/web/templates/index.html` next to `.modal-small`.
