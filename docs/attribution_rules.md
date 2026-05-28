# Attribution Rules

Pragmatic defaults for resolving messy signup attribution before marts/analytics.
Implemented in `int_user_attribution` / `int_user_revenue`.

## Models

| Model | Meaning |
|-------|---------|
| **Last-touch** | Credit goes to `attr_channel_last_touch` — the channel most recently engaged before signup. |
| **First-touch** | Credit goes to `attr_channel_first_touch` — the channel that started the journey (media acquisition story). |

Both models are computed side-by-side. We never collapse conflicts into a single “winner” at this layer.

## Channel resolution order (per touch)

For each of first-touch and last-touch:

1. Explicit touch field (`first_touch_channel` / `last_touch_channel`) if it is a known channel
2. Else `utm_source` if it is a known channel
3. Else `referral_source` if it is a known channel (`youtube`…`referral`)
4. Else `'unknown'`

Known channels: `youtube`, `twitter`, `instagram`, `newsletter`, `podcast`, `blog`, `organic`, `referral`.

Non-channel referrals (`direct`, `word_of_mouth`, empty) are **not** used as channel labels; they only affect conflict/confidence flags.

## Conflicts & missing data

| Situation | Handling |
|-----------|----------|
| `first_touch != last_touch` (~38% of users) | Keep both channels; set `has_touch_conflict = true` |
| Missing UTMs | Do **not** drop the user; resolve via touch/referral fallbacks |
| `referral_source` vs `utm_source` disagree | Set `has_referral_utm_conflict = true`; channel resolution still follows the order above |
| No usable channel signal | `attr_channel_* = 'unknown'`, confidence `low` |

## Attribution confidence

| Level | Criteria |
|-------|----------|
| `high` | Both touch fields present, `utm_source` present, no touch conflict, no referral/UTM conflict, channels not `unknown` |
| `medium` | At least one touch field present, channels resolved, but missing UTM and/or a conflict flag |
| `low` | Either resolved channel is `unknown`, or both touch fields missing |

## Campaign linkage

- Join `utm_campaign` → `campaign_metadata.campaign_slug` (slug = `lower(campaign_name)` with spaces → `_`, matching `generate_data.py`)
- If `utm_campaign` is null/unmatched → `campaign_id` is null; channel attribution still stands

## Content linkage (best-effort)

- Consider content published in the **30 days before** signup
- Prefer same channel as the resolved touch, then same `utm_campaign`, then most recent `publish_date`
- Separate IDs: `content_id_first_touch`, `content_id_last_touch`
- Unmatched → null (common; not treated as an error)

## Revenue inheritance

All monthly revenue rows for a user inherit **signup-time** attribution from `int_user_attribution`.

We do **not** re-attribute revenue months when later content performance changes. `months_since_signup` supports cohort/retention analysis.

## Trade-offs (why first-touch + last-touch)

- Signups only expose first/last touch — not a full multi-touch path — so linear / time-decay / position-based models would be artificial 50/50 splits
- ~38% first≠last means the two models diverge enough to be analytically useful
- First-touch aligns with “which content started acquisition”; last-touch aligns with “what closed the signup”
