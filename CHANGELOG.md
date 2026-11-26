# Changelog

The running version is shown next to the logo in the web app, in *Settings*, at the top of
every report, and with `nexus --version` (`valcoach --version` up to 4.4). Update: `git pull`, `pip install -e .`,
`sudo systemctl restart nexus` (or `docker compose up -d --build`). `data/` and `config.toml` aren't touched.

## 4.85.0
- **Match-day ping on Discord** (Premier › *Brief before each match* › *Match-day ping*, with the time to send it,
  12:00 by default): on the match days, once a day between that time and the match, it posts:
  - the time and the map (or *Playoffs today*);
  - who's playing: confirmed out of 5, maybe, who can't play and the sub for them;
  - the players who haven't answered yet, pinged (the ones with a Discord ID set under Availability);
  - the boards against opponents on the map, and when the brief comes (if it's on).
  - *Send the match-day ping now* posts the next match day's ping by hand, with the link to the availability page.
- The brief 60 minutes before the match stays as it was: the ping is the heads-up earlier in the day.

## 4.84.0
- **Did the prep work?** The boards you draft against a scouted team (*Draft a plan in the strat book*, 4.79) are
  checked against the rounds you tag with them in review evenings.
  - **Review evening** of a match against that team: the boards come first in the round's strat pick, marked ★. The
    summary gets *Your prep against them*: each board, the rounds you ran it in and how many you won, or that it
    wasn't tagged in any round. The summary's Discord post includes it too.
  - **Strat book:** a board's card shows *Prep against Rivals · won 3 of 4 rounds* (plus its rounds against others).
  - **Their scouting page:** under each map, your boards against them with their record.
  - New evenings store the opponent's Premier id, so the boards are found even if the team renames itself; older
    evenings use the match's review or the name and tag.

## 4.83.0
- **Lineups for your strats:** the coach goes through every ability your side has on a strat board, step by step,
  and puts the matching lineup from the team's lineups library next to it, with the clip. It matches the agent and
  ability, the site it lands on, the side, and the callout in the lineup's name.
  - **Strat page:** a *Lineups for this strat* card under the board, e.g. *Execute A: Sova (Manuel) · Recon Bolt →
    A Main ▶ Dart A Main*. If the library has nothing for an ability, it names a lineup your team throws in its
    replay files (*add it*), or asks you to add one.
  - **Match screen:** under each strat, your own lineups first (your comp agent or your name on the agent token),
    each with *practise in 3D* or *record in 3D* (the lineup trainer, 4.81); the rest are folded below.
  - **Discord:** posting a strat step adds that step's lineups, each clip as a link.

## 4.82.0
- **The week ahead:** every practice and match day of the next 7 days in one place.
  - **Sunday team report:** the *Next* field (only the next match) is now *The week ahead*, one line per day from
    Monday to Sunday. Practice days show their time to end (from *Practice › Settings*) and what the plan has on
    them once the week's plan is made. Match days show the time, the map played that day (playoffs too), and who's
    confirmed from availability, including who can't play and the sub. Below that come the boards drafted against
    opponents for each map played.
  - **Practice page:** a strip with today and the next 6 days, each with its practice and match (time, map,
    confirmed out of 5).
  - Match days come from the match-day brief; until they're set, Saturday and Sunday are used, as on the
    availability page.

## 4.81.0
- **Lineup trainer** (Practice › Aim on maps › *Lineups*):
  - **Record:** pick the map, agent, ability (C, Q, E, X) and a name; you start on the 3D map, walk where you throw
    it from, aim (crouch if the lineup is crouched) and press your shoot key: where you stand and look is saved.
    Press it again to save it over.
  - **Practise:** all lineups of a map, or one. Each rep starts a few metres from a lineup, its spot a ring on the
    ground; walk onto it, aim and throw (your shoot key). A rep is how many degrees your aim was off; more than
    0.6 m off the spot is a miss. After each throw the right aim shows as a marker. The result lists each lineup;
    sessions go into the charts, goals and your week in degrees like the other drills.
  - **From your strat book:** the abilities your team's strats draw that you have no lineup for yet, with the
    callout they land at, each with *record it*.
- Your week on Aim on maps now shows degree drills (crosshair placement, lineups) in degrees (it showed seconds).

## 4.80.0
- **Sunday team report on Discord.** A new switch under *Practice › Team practice*: Sundays at 20:00 (or *Post the
  team report* any time) the week goes to the weekly-focus channel in one post:
  - **📒 Strats:** the rounds tagged with strats in this week's review evenings and how many you won, your best
    strat so far (5 rounds or more) and the ones struggling (35 % or less, with how often the utility went in as
    drawn).
  - **💰 Economy:** the rounds where the buy didn't fit in the week's matches (Premier reviews and reviewed
    matches), counted and with their rounds ("2× a lost force that broke the next round (1 lost): Ascent vs RV R4; …").
  - **🎯 Drills:** sessions per player, the biggest step, goals reached and who didn't drill (the full drill week
    stays its own post).
  - **🗓️ Next:** the next match day and time, the week's map and the boards drafted against opponents for it.

## 4.79.0
- **Prep against an opponent in the strat book.** On a scouted team's page (Premier › Opponents) each map has
  *Draft a plan in the strat book*. It adds two boards to your strat book for that map:
  - **vs TAG: their setup** (your attack): their defenders drawn as enemies where they stand at the first fight
    (their agents on that map), the site with the fewest of them marked, and a call ("They stand 2 A · 1 B · 1 Mid.
    Hit B (the fewest of them). They lose retakes on A: plant A and play post-plant. …").
  - **vs TAG: their hit** (your defense): their five where they go on full buys (stacked in one zone, or spread
    and hitting their main site), the main site marked with its share, and a call ("They hit B 86 % of plants,
    fast (stacked B). Stack B, rotate from the other site on contact.").
  Their scouting lines go into the notes. Edit them like any strat; pressing it again doesn't double them.
- **The match-day brief** lists the boards drafted for the map under *Against your opponents*.

## 4.78.0
- **Opponent scouting: how they play their rounds.** A scouted team's page (Premier › Opponents) gets *How they
  play their rounds* on each map, split by their buy (pistol, eco, force, full buy):
  - **Attack:** rounds won, which site they plant (shares, and rounds without a plant), the median plant time and
    first fight, and how they stand at the first fight: stacked (4 or more in one zone, which one) or spread out
    (a default).
  - **Defense:** rounds won, how they stand at the first fight (players per zone, "2 A · 1 Mid · 2 B") and how often
    they look for early picks (the first fight before 20 s, out of their sites, and where).
  Positions come from the kill events (everyone's position at the round's first kill). What stands out, with 4 or
  more rounds behind it, goes into the "how to play them" lines on their page, the match-day brief and the match
  screen ("Ascent attack, full buys: B 86 % of their plants, fast hits (4 of 7 planted in 35 s), stacked on B at
  the first fight."). Teams scouted before 4.78: press *Scout again* (their matches are cached, so it's quick).

## 4.77.0
- **New drill: Crosshair placement** (Practice › Aim on maps, on every site). You're walked along the attackers'
  route at walking speed, so only your aim counts. A head shows on each hiding place defenders used in your
  replays the moment it comes into view (then disappears after 1.4 s, or when you shoot it), and where your
  crosshair was right then counts: degrees off the head, above or below. A rep is the median of them; lower is
  better. The result shows your height on average ("1.6° too low"), how many you had within 2° and the worst one;
  the minimap colours each place. Default 5 reps; the warm-ups, the session charts, goals and the weekly view count
  it in degrees ("3.4°", "0.8° closer").

## 4.76.0
- **Economy review, round by round.** For one match: your team's money per player (loadout plus credits left: what
  each had to spend) against what it bought, and the rounds where the buy didn't fit:
  - half the team bought, half saved (2+ on 3000+, 2+ under 1500)
  - an eco or force while 4 or more had the money for a full buy
  - a lost force that broke the next round (no full buy after it)
  - a lost full buy with no rebuy the round after
  - one player off the team's buy: bought while the team saved, or saved while it bought (named)
  Pistol rounds aren't judged, and a lost buy just before the half's switch doesn't count against the next round.
- **Review evening:** each round shows *Money* (per player, and what was bought) and, where it didn't fit, *Buy* in
  amber; the summary gets an *Economy* list ("1× a lost force that broke the next round (round 4; 1 lost)").
  Evenings from before get it too (worked out from the match).
- **Premier match review:** an *Economy* card with every round as a cell (P pistol, E eco, F force, B full buy; won
  or lost; ! where the buy didn't fit, the reason on hover) and the same list.

## 4.75.0
- **Strat win rates.** Every round you tag with a strat in a review evening (*Strat this round*, 4.74) now counts
  for that strat:
  - **Strat book:** each card shows how often you ran it and the rounds won ("Ran 9 rounds · won 5 (56 %)", with a
    bar), and whether the utility went in as drawn ("Utility as drawn in 5 of 8 · won 4 of those, 1 of the other 3").
    Under 5 rounds it says "few rounds yet". Each map names its best strat per side among those run 5 times or more.
  - **A strat's page:** the same numbers, and its rounds (won/lost, opponent, round number); a click opens the
    review evening at that round.
  - **The evening's strat pick** shows each strat's record next to its name.

## 4.74.1
- The *open it* link next to *Strat this round* (review evening) no longer takes its address from the page: it's the
  strat's page next to the evening, with the strat's number checked (a CodeQL alert from 4.74.0).

## 4.74.0
- **Scrim review.** The review evening (*Practice › Review evening*) now checks a match against your plan:
  - **Your comp against the plan**: the agents you played against the draft marked *our comp* for that map, with who
    wasn't played and who was played instead (or "played as planned").
  - **Where each kill was**: the killer's and the victim's callout next to every kill.
  - **Utility per round**: each player's C, Q, E and X casts in *Our players this round* (when Riot's data has them).
  - **Strat this round**: pick the strat you ran (your strat book's strats for the map and that side; everyone sees
    the pick). It lists the abilities the strat draws, per agent, against what that agent used in the round
    (✓ / ✗, or "not played").
- **Scrims link to their match.** A scrim in *Practice › Scrims* whose match is in your games (the same day and map,
  two or more of you in it; the score decides between two) gets *Review it round by round*, which opens the review
  evening on that match.
- Needs a new evening: ones started before 4.74 have no comp check, no callouts and no utility per round (the strat
  pick works in them too).

## 4.73.0
- **Every drill's sessions as a chart.** On Practice › Aim on maps, a spot's card now draws your sessions of that
  drill (the last 20): the median of each session as a dot on a line, the best one marked, the day of the first and
  the last below, and which way is better. Your goal on that drill is a dashed line with its day ("goal 3.50 s by
  29.11.", "✓" once reached). Hover a dot for its day, its median and how many reps you won. The same chart is on
  the drill's result screen, with the session you just played in it.

## 4.72.0
- **Retakes like in the game.** The attackers no longer stand still on their places. Two of them hold a crossfire
  on the spike (the widest angle between the places attackers played the spike from in your replays, preferring
  places that can see it), one of them shifts to another place after 3 to 8 seconds, and a defuse is heard: whoever
  can't see you peeks the spike a moment later. So a tapped defuse baits them out, a full defuse into an unchecked
  angle gets you killed ("Killed on the spike"). Half a defuse still stays.
- **His view after a lost duel (every drill).** When an enemy gets you, the last three seconds play again from his
  eyes, a bit slowed down: you as an agent, where you were and what he saw, how long he had you, and why you lost
  it (you were moving, on the spike, reloading, he saw you first, you never saw him). Your *next* key skips it;
  *Options & keys › After a lost duel: his view* switches it off. In death drills too (your killer from the replay).

## 4.71.0
- **Trainer settings from the game.** The Nexus app now reads your VALORANT settings on your PC and sends the ones
  the trainer uses: your sensitivity, your crosshair (the profile you use, colour, outlines, dot, inner and outer
  lines) and your keys (shoot, aim, reload, moving, walk, crouch, the spike and your C, Q, E abilities, both key
  slots, mouse buttons and the wheel). They come from the Riot Client while it runs (the ones Riot keeps online, so
  always the current ones), else from VALORANT's files of the account you used last. Sent when they change, nothing
  else of your account. Switch: *This PC › VALORANT settings*.
- **Practice › Aim trainer** shows them (*From VALORANT: sens, crosshair, keys, when read*). *Keep in step with the
  game* is on by default: a change in the game is taken over into the trainer and the drills (Aim on maps). Changed
  something in the trainer by hand? It stays until the game's settings change again, and the bar shows what's
  different, with *Use the game's*. Not taken over: keys with Shift/Ctrl/Alt and keys set for one agent only.
  The trainer's own keys (restart, next, watch, full screen) move to a free key if the game uses theirs.

## 4.70.2
- **Glass boxes are solid.** In maps built from the game's files, every face with a glass material was see-through:
  enemies in the drills saw you and shot you through glass crates (Abyss's B site boxes), and you could see them.
  A piece of glass shaped like a box (every side at least 40 cm and at most 4 m) is now solid like any box: drawn
  opaque, and it blocks sight, shots and the way. Thin glass (windows, panes, doors, railings, glass floors) stays
  see-through. Needs the maps built again: `nexus build-game` (the map format is now version 9; the log says
  "N glass boxes made solid").

## 4.70.1
- **Drills: hits that didn't count.** Whether a wall is between you and the enemy you shoot was decided on a coarse
  see-through grid (0.5 m cells, every cell that touches a wall or a box counted as solid), so walls and boxes
  were up to half a metre thicker than drawn. A head or shoulder just past a box edge or a corner (where enemies
  hide in retakes, post-plants and entries) often showed MISS with the crosshair on it. Now, when the grid says
  "blocked", the drawn map decides: Nexus draws it along your shot into one pixel off screen and reads how far the
  first wall is; the shot counts if he's in front of it. (On the real Ascent map about 1 in 10 clear lines near
  walls was wrongly blocked.)
- **Drills: the yellow ball.** Your team's flashes, stuns, recon darts and traps (4.65) were drawn as a ball where
  they popped, often right where you stand. They aren't drawn any more (they still work); their smokes, walls and
  mollies are.

## 4.70.0
- **Drill goals.** *Your goals* on Practice › Aim on maps: a drill, a target and a day ("Retake · Ascent · Retake
  B: under 3.50 s by Sunday"). Ideas come from your week (back to where a slipped drill was, or a step further on
  one that got better); change the target or the day before you add one. A goal is reached by the first session
  whose median makes it, and stays reached. Each goal shows where you started, your best since, a progress bar and
  *Play it*; at most 6 open goals. The coach (Ask the coach, the weekly letter) sees them, and the Sunday Discord
  post lists the goals reached that week.
- **Drills in the team's practice plan.** Team › Practice has *Drills this week*: one drill per starter (his open
  goal, else the drill that slipped most, else the match warm-up on the week's map, else the daily warm-up), with
  *Play it* for your own. It ticks itself after 3 sessions of it this week.

## 4.69.1
- **Map prep: every map.** Map prep listed only the maps that have map angles; now every map is there. A map
  without map angles gets the warm-up, your weakest skill and its callouts quiz.
- **Map angles: more maps.** A site is also found when the map data names it otherwise (a lower-case site letter,
  a site callout not in the region "Site", "A Site" / "Site A" / "A Plant"), and on big or open maps the spots in
  front of you are looked for wider and further before a map is left out. The maps still missing are named under
  Map angles, with why ("no sites in its callouts", "too few callouts around its sites", …).
- **Perfect sens: count my normal scenarios too** (a switch in the Sens finder, off by default). Runs now remember
  the sens they were played at. With the switch on, every scenario you played at 2 or more different sens values
  in the last 90 days adds points to the sens curve (your scores there scaled to your best), at half the weight of
  a sens-test round. Runs made harder or easier by a skill session and map angles don't count.

## 4.69.0
- **Your week from the coach.** On top of Ask the coach: once a week, a short letter about your games and your drills
  together ("your B retakes got faster, and you won 3 of 4 games on Ascent"): this week's games against last
  week's, the maps and agents you played, what you drilled and what got better or slipped. Under it 2-3 things for
  the coming week and the drill to play first, with a link to Aim on maps. *Write this week's letter* writes it now;
  *Every Monday by itself* writes it Monday mornings (the automatic-jobs model, Settings › Models) and sends a
  notification to your devices. The last 8 letters are kept.

## 4.68.0
- **Match-day warm-up.** Next to *Start the warm-up*, Aim on maps shows *Match warm-up: <map>* for each of your
  teams with a Premier week map. Its drills are all on that map. If you picked the opponent under *Against* on
  the comps page: holding the angles of the site they attack most, retaking it, then the entry and post-plant
  on the site whose retakes they mostly lose, and a tracking drill. Without an opponent: the map's most fought
  spots.
- **Strats for the counter style.** The strat book has *Against* too (the same pick as on the comps page): per map
  the counter style, your strats that fit it ("Defensive defense: B stack") and what's missing, with *Draw one*
  to start it. Every strat has a style: set it on its card or when you create it; without one, Nexus guesses it
  from the name and notes ("rush", "stack", "execute", …) or from how much utility it draws ("looks defensive").

## 4.67.1
- **The drag & drop editors on a phone** (agent pool, ideal compositions). Checked at phone size with touch:
  - 4 agent tiles a row instead of 2, so you don't scroll through a long list.
  - A swipe over the tiles scrolls the page again; hold an agent a moment (0.3 s) to drag it. With a mouse it's
    as before.
  - Dragging near the top or bottom of the screen scrolls the page, so you can drag an agent from the end of the
    list up into your pool.
  - Tap an agent in *Can play* or *Won't play* to put it at the end of your pool.
  - Opening the ideal composition editor no longer hides its first line under the top bar.

## 4.67.0
- **Daily warm-up.** *Start the warm-up* on Practice › Aim on maps plays up to 6 drills in a row, about 10
  minutes: the drills that slipped this week, the ones your newest match points to ("practice what cost you
  rounds"), the tracking drill you played least, then drills you got better at, to keep them. Shorter than usual
  (e.g. 10 reps for holding an angle, 3 retakes); the drill page says "Warm-up 2/5" and *Next drill* goes on. Any
  drill can now have general drills and your deaths in one queue.
- **The team's drill week on Discord.** Team › Practice: *Weekly drills summary on Discord* posts every Sunday at
  20:00 (to the weekly-focus channel) who drilled how much (sessions, reps, days), each player's biggest step,
  the team's biggest step, who didn't drill yet, and how many sessions were on this week's map and which kinds
  of drill nobody played there. *Post this week's drills* posts it right away.

## 4.66.0
- **The coach knows your practice.** Ask the coach (and the team coach) now gets your drills from Aim on maps:
  when you last drilled, sessions this week and last week, how many of the last 8 weeks you drilled, each kind
  of drill this week against last week ("Retake: 3.40 s, 1.60 s faster"), and what got better or slipped. It ties
  that to your games: praises what got faster, points to what slipped or what you never drill when your games
  show the problem, and names the drill to play.
- **Counter comps from scouting.** On the comps page, *Against* lists the teams you scouted (Premier › Division).
  Pick one and every map gets the comp style that counters them there, from their own games: they hit fast or
  stack one site (*Defensive*), they lose retakes or hold sites slowly (*Utility execute*), they have no
  initiator (*Aggressive*), their entry player wins his duels, two duelists, which side they're better on. A box
  shows why and their usual comp on the map. Picking a style yourself still wins. The scouted team's page shows
  the counter per map, with a link to the comps against them.

## 4.65.0
- **Drills: your week.** At the top of Practice › Aim on maps: how many drill sessions you played each of the last
  8 weeks (Monday to Sunday), this week's sessions, reps and days, and per kind of drill (hold, retake, tracking, …)
  this week against last week: the median of your reps, "0.06 s faster" or "+5 points". Under it the drills that
  got better and the ones that slipped this week against the weeks before, each a link to play it again. Runs now
  keep the map and the spot's name so the list can say "Retake · Ascent · Retake B" (older runs show the kind).
- **Drills: your team's utility.** In the general drills with utility on (hold, attack, entry, retake, post-plant)
  your own team's utility from the same round of your replays plays too, not only the enemies': their flashes and
  stuns hit the enemies, their recon shows them, their smokes and walls block both sides, their mollies burn the
  enemies (and you, if you stand in them). The start screen says how many rounds bring your team's utility.

## 4.64.0
- **Agent pool: a role filter.** *All / Duelist / Initiator / Controller / Sentinel* above *Can play* and *Won't
  play*, so you find the agent you want to drag without scrolling through all of them.
- **Agent pool: agents on some maps only** ("Viper only on Breeze and Icebox"). Every agent in your pool has an
  *All maps* button: pick the maps you play it on. With *Follow our agent pools* on, the comps page (every mode,
  drafts, Discord prep) only gives you that agent on those maps; the cards say "plays it on other maps only". The
  team's pools show "2 maps" next to such an agent (hover for which).

## 4.63.0
- **Comp sheet: ideal compositions with drag & drop.** *Edit* (or *Set by hand*) on a map opens an editor right
  under it, instead of five dropdowns: 5 slots, and every agent below as a tile with how many of your players have
  it in their pool (hover for who; "nobody" in red), filtered by role if you like. Drag an agent into a slot, or click
  it to fill the selected slot; drag slots onto each other to swap them, or out of the row to clear them (or ✕).
  Keyboard: Enter picks, ← → move a slot, Delete clears. The role mix (e.g. 1D 2I 1C 1S) shows as you go, and it
  saves by itself once all 5 slots are set. *Done* refreshes the map with who plays what.

## 4.62.0
- **Comp styles.** The comps page has a *Style* switch: *Balanced* (as before), *Aggressive* (fast hits and early
  fights: entry duelists, flashes, stuns; a second duelist is fine), *Defensive* (holding sites and retakes: set-ups,
  recon, flank watch; a second sentinel is fine) and *Utility execute* (set-piece site takes: smokes, walls, flashes,
  damage; a second controller is fine). Each agent gets points for how well it fits the style, on top of the
  player's own numbers, so players are still put on agents they play well; the cards say "fits an aggressive
  style". The comps at a glance, the other options, the fill-ins and *Use this comp* all follow the style. A role
  mix you set in the team's map meta still comes first, and *Most comfortable* doesn't use styles.
- The style is kept per team for your login; drafts made from a suggested comp use it too.

## 4.61.1
- **Code scanning** (three high alerts on main):
  - *Uncontrolled data used in path expression* (`web/replays.py`, `stats/drills.py`): the match cache and the
    drills cache only take a match id (letters, digits, `-`) as the file name, and the path is checked to stay in
    its folder (`safepath.safe_join`, like the other caches). Anything else isn't read or written.
  - *DOM text reinterpreted as HTML* (`aim_maps.js`, the spot card): the number of reps comes from your saved
    settings in the browser; it's now always a number, and every value on the card is put in escaped.

## 4.61.0
- **Comps: the other options as cards, with the why.** Under the best comp of a map, 3 other options (was 2), each
  as five small cards like the big ones: the agents that change from the best comp stand out ("was Omen"), the
  same ones step back. Under them, why each swap could make sense (the player's games and win rate on it on the map
  and overall, his agent pool rank, the map rules), how far the option is behind the best (*close to the best*,
  *a bit weaker*, *a fallback*) and when you'd pick it: an agent of the best comp doesn't work out, you want more
  smokes / more entry power, who needs practice first, the web source's note.
- **Use this comp**: saves the option as a draft marked *our comp* for the map (an older *our comp* goes back to
  *trying*), so the Discord prep and the match-day availability use it. The comps page shows which comp is yours.
- Drafts: *Start from a suggested comp* lists the same 4 comps as the comps page.

## 4.60.0
- **Comp sheet: a new agent pool editor.** You see your own pool first, big: every agent is a tile (icon, name,
  games), your pool in order (best first, green to red), then *Can play* with every other agent (no more adding them
  one by one) and *Won't play*. Drag tiles between them and within your pool, with the mouse or on a touch screen,
  or with the keyboard (← → move, Enter in / out of the pool, Delete: won't play). It saves as you go ("saved").
- **You edit only your own pool.** Before, the team owner could edit everyone's. Now each player edits his own
  (linked by the in-game name under *Account*, or by the owner in *Team settings*); the owner keeps only the pools
  of players nobody is linked to (*Edit for them*), since they can't do it themselves.
- **The team's pools behind a switch** (*The team's pools*, remembered): the others read-only, a column each, top 8
  and *Show all agents*. On by default when you aren't linked to a player.

## 4.59.1
- **Code scanning** (the high alert "DOM text reinterpreted as HTML" in aim_maps.js from 4.58.0): the spot card
  (your agent's abilities, the options) and the *Practice what cost you rounds* box put everything into the page
  escaped. (The 4.59.0 pull request didn't show it again because code scanning only lists new alerts there; it was
  still open on main.)

## 4.59.0
- **Practice what cost you rounds.** Aim on maps opens with your last match: every spot you died at, as the drill on
  that spot (died retaking B → *Retake B*; died after planting → *Post-plant*; died holding an angle → *Hold* on it;
  died going onto a site → *Entry*, elsewhere as an attacker → *Take* the spot), the most deaths first, with the
  rounds. Click one: it opens that tab, map and spot, ready to play. A match's report has a button for it too
  (*Practice what cost you rounds*), with that match.
- **Your progress on each spot.** Every spot in the list shows a small line of your sessions (the median of each,
  green when it's getting better), and the spot shows the first sessions against the last ones ("6 sessions: 2.41 s →
  1.87 s better") next to your best.
- The drills of every match are worked out once more in the background (they now keep whose death each fight was).

## 4.58.0
- **Your own abilities in Aim on maps** (hold, attack, entry, retake, post-plant). Pick **Your agent** on the spot
  card; in the drill their C, Q and E are on your keys (*Options & keys*: Ability C on Z by default, since C is
  crouch here; Q and E on Q and E), quick-cast where you aim, with the agent's charges for the rep. Ultimates aren't
  in the drills. What they do:
  - **Smokes** (Omen, Brimstone, Astra, Clove, Jett, Viper, Harbor, Cypher's cage) block their sight and yours.
  - **Flashes** (KAY/O, Phoenix, Skye, Reyna, Yoru, Gekko, Vyse, Omen's Paranoia; Breach's Flashpoint through
    walls) pop where you aim after the agent's delay: anyone facing it is blind for about 2 s and can't fight you.
    Look away from your own: it blinds you too.
  - **Mollies** (Brimstone, Viper, KAY/O, Killjoy, Phoenix, Raze, Gekko, Sova's Shock Bolt, Breach's Aftershock…)
    burn whoever stands in them, at close to the game's damage: molly the spike in post-plant. Yours burns you too.
  - **Concuss, nearsight, tethers** (Breach, Skye, Neon, Fade, Astra, Deadlock, Tejo): they can't fight you for a
    few seconds.
  - **Recon** (Sova's dart and drone, Fade's Haunt, KAY/O's knife, Cypher's camera, Killjoy's turret, Tejo's drone)
    and **traps** (Cypher, Killjoy, Chamber, Deadlock): revealed enemies show on the minimap; a trap also catches the
    first one who walks into it.
  - **Walls** (Sage, Viper, Phoenix, Neon, Harbor, Deadlock, Iso, Vyse) block sight across where you aim.
  - **Movement**: Jett's Tailwind, Raze's Blast Pack and Waylay's Lightspeed dash; Omen's Shrouded Step teleports
    where you aim; Chamber's Rendezvous, Yoru's Gatecrash and Waylay's Refract leave a marker and take you back on the
    second press; Neon's High Gear makes you faster.
  - Abilities that don't change a fight in a drill (heals, decoys, slows) aren't in it. Your abilities and their
    charges show next to the ammo.

## 4.57.0
- **Ask the coach picks the games your question is about.** Before answering, the coach sees all your stored games
  (how many per mode, agent and map, from when to when, the newest ones one by one) and picks the ones the question
  needs: "my last two Premier games", "KAY/O or Clove lately?", "Summit this month". Those games go into its data one
  by one (mode, map, agent, result, K/D/A, ACS, ADR, KAST, first kills and deaths, headshots) plus what they add up
  to, by agent when there's more than one. A question that isn't about particular games keeps the usual picture.
  It always sees your newest 8 games too. Under the answer: *Games: …* says which ones it used.
- **A player who changes their Riot ID keeps their profile.** Each import checks who the account is now (by its
  account id from your games); if the name changed, the profile takes the new name and keeps its games, drills and
  notes. If you had already added them again under the new name and that player has no games yet, it's folded in
  (its team place goes to the renamed player). If both have games, the import says so and leaves them alone.
- German texts.

## 4.56.3
- **No more seeing enemies through walls in Aim on maps.** The replay viewer's *Outlines* (players behind walls drawn
  faintly) is saved in your browser and the drills used the same setting: once it was on in a replay, enemies showed
  through walls in the drills too. A drill never draws them now; the replay viewer keeps your setting.

## 4.56.2
- **Summit (and every map that comes out later) shows up.** The list of maps from valorant-api.com (callouts,
  minimaps, where things are on them) was downloaded once and never again, so a map released after that was missing:
  no Map angles or Map prep for Summit, and no callouts or minimap for Summit matches. Now the list is fetched again
  when it's older than a week (offline: the old one stays, and it tries again at most once an hour; a broken download
  never replaces it).
- **Map angles on maps that name their callouts differently**: a site without a callout called *Main*, *Lobby* or
  *Link* uses the site's callout furthest from it (within reach) as the way in.

## 4.56.1
- **Smokes are solid in the drills**, as in the game: you could see the enemy through a smoke (it blocked sight for
  the drill already, but it was drawn see-through and the enemy model was drawn anyway). Now smokes and walls are
  opaque in Aim on maps (and in the death drills), and anyone whose head and chest are both behind a smoke isn't
  drawn. The replay viewer keeps them see-through.

## 4.56.0
- **The enemies use their utility in Aim on maps** (hold, attack, entry, retake, post-plant). Each rep takes one real
  round's worth of what their side threw around these fights in your replays (now and then a round without), at its
  real time and place:
  - **Retake / post-plant**: from the plant, on the spike's clock. The post-plant mollies on the spike, the smokes on
    the way in, the retakers' flashes and smokes.
  - **Hold**: from the peek. A flash thrown just before the swing pops before it (the peek waits for it).
  - **Attack / entry**: when you get there, as far ahead as it was thrown before the fight.
  - What it does: **smokes and walls** block sight both ways (you can't walk through a wall either), a **flash**
    blinds you if it pops in front of you while you look (look away), **mollies** burn you (you have 150; 24 to 60 a
    second depending on the agent, close to the game: defusing in one is how retakes are lost), **slows** halve your
    speed, **recon** (a dart, a Haunt) and **traps** reveal you: the enemies pre-aim, react quicker and don't need to
    be looking your way.
  - Your health, *revealed* and *slowed* show next to your ammo.
- On the spot: **Their utility** on / off, with how many rounds it comes from and what they throw (smokes, flashes,
  mollies, …).
- The drills of every match are worked out once more in the background (they now keep the utility around each fight).
- German texts.

## 4.55.0
- **Your keys in the aim trainer.** The trainer now uses the same keys as Aim on maps (saved with your account): shoot
  (any mouse button, key or the wheel), start / go on / next scenario (Space by default, Enter still works when
  paused), play it again (Backspace) and full screen (F). A **Keys** button next to *Crosshair* opens them inside the
  trainer; the start screen shows the keys you have.
- **Movement abilities in the replay viewer.**
  - **Teleports** (Omen's Shrouded Step and ult, Chamber's Rendezvous, Yoru's Gatecrash, Waylay's Refract) jump
    instead of sliding through walls, with a puff in the agent's colour where they left and where they came out. The
    model stands still around the jump instead of running on the spot.
  - **Dashes** (Jett's Tailwind, Waylay's Lightspeed) take one long stride with a short trail; **Updraft** and
    **Blast Pack** leave a puff on the floor where they took off.
  - **Sprinting**: anyone faster than running (Neon's High Gear, Reyna's Dismiss) plays the game's sprint animation.
  - Which ability it was comes from the replay's casts. Without them (or for an agent not on the list), a jump of more
    than 6 m in a moment nobody can run is still drawn as a teleport.
- **Server:** `nexus build-game` once (without `--force`) adds the sprint animations (`TP_Core_Sprint*_LB` in
  `Characters/_Core/3P/Anims`, already in a full `_Core` export). Without them a sprint plays the run animation.
- German texts.

## 4.54.0
- **Practice › Aim on maps: entry, retake and post-plant.** Three new tabs next to *Clear a site*, on the same real
  spots from your replays:
  - **Entry**: you're first onto the site on the attackers' most used route. 1 to 3 defenders (you pick) wait on the
    places defenders hid in your replays, only ones you can see from somewhere on the way in; one of them swings you
    when you get close, and whoever's still hiding comes out when you reach the site. Your time: from the start until
    the last one is down (out of time after a minute).
  - **Retake**: the spike is down where it usually is on that site, with the time it had left when defenders set off
    in your replays. You come back in on one of their real ways (up to three, rep by rep, drawn on the minimap), 1 to
    3 attackers play it from the places attackers used after planting. Kill them and **defuse**: hold your defuse key
    on the spike (4 by default, like the game; 7 s, half of it stays, you can't move or shoot meanwhile). The spike
    goes off at 0. The result shows what was left on it.
  - **Post-plant**: you play the spike from the places attackers used (the three most used, rep by rep), looking
    where retakers first show up. 1 to 3 retakers come in on their real routes at their real speed (a few seconds
    apart), then go for the spike and defuse. Kill each before he has you for his reaction time (the difficulty),
    and before anyone finishes a defuse. Your time: how fast you got each of them once he could be seen.
  - The spike is drawn in the map (blinking faster under 10 s) and on the minimap.
- **The route on the minimap is easier to see** (clear a site, entry, retake): thicker, with a dark edge on any map,
  an arrow at its end, and the part you've already walked faded.
- **Your keys**: *Defuse (hold)*, 4 by default.
- The drills of every match are worked out once more in the background (they now keep where the spike was and the
  defenders' ways back in after a plant).
- German texts.

## 4.53.3
- The last two code scanning alerts: the review evening puts each player's mark into the page escaped, and the roster
  drafts' picture that follows the pointer while dragging an agent is a copy of the picture you picked up (no
  address built from the page).

## 4.53.2
- **3D maps from the game's files: no frame round the spike sites.** The low "fence" round where the spike can be
  planted is the game's site marker (`BombsiteMarker_0_BombsiteA` and its glow: a glowing line on the floor in the
  game). It's left out now, and so are the spawn barriers (they're gone once the round starts).
- **While a map is built again** (a new version, like this one), the pages keep showing the map from the game's
  files built before, instead of the rough one from the replays; a map from the game's files that isn't built yet
  shows "being built" and loads by itself when it's ready. The one from the replays is only used where the game's
  files don't have the map (or it can't be built).
- The maps are built again once (`nexus build-game --force` to do it now).

## 4.53.1
- **3D maps from the game's files: missing floors.** Objects were left out as clutter when a word for clutter was
  anywhere in their name: Haven's Bird House (the floors and walls of "Floor_8_BirdHouse…" read as a bird), planters,
  Corrode's castle wall (…Wall**CUp**per read as a cup), Split's and Ascent's scaffolding. Now the name's words count,
  a floor, wall, roof or stairs is never clutter, and things like pipes, plants or debris are only left out when
  they're small (under 6 m). On Haven 1,530 cells of walkable floor had nothing below them; now 55.
- **The fence round the spike sites** (the glowing site border, an effect) is left out.
- **No floor behind thin walls**: the floors of the geometry are only joined to where you can walk without going
  through anything (the ground behind a map's outer walls isn't part of it).
- **Replays: living again in a round.** Clove's ult (she comes back after dying) and Sage's resurrection: the
  replay showed the player dead from the first death on, so you lost Clove, her kills looked like the other player
  just falling over, and you couldn't watch through her eyes. Each player now has his lives in a round: he's back
  when the replay has him again after dying (after a pause, or moving away from where he fell, or casting his ult),
  and dead again at his next death (the match's kills, or the replay's own when the ult runs out). The 3D replay
  draws him, follows him, puts him on the minimap and in the top bar again; his body and the X only stay while
  he's dead. The Combat Report's "who saw whom" counts him as alive again too.
- The maps are built again once by themselves (`nexus build-game` to do it now).

## 4.53.0
- **3D maps from the game's files: solid boxes and bridges.** Where a map is built from the game's files, where you
  can walk now comes from the files alone, no replays:
  - The game's navigation mesh, without the parts that run under boxes and walls: you no longer walk or fall
    through them.
  - The floors of the geometry itself that you can get onto from there, one step at a time (at most 1.3 m up, a
    jump): box tops, bridges and walkways, ledges, the strip along the walls. Not roofs or the tops of walls, and
    nothing a player can't stand on (railings).
  - Glass stays see-through but is solid to walk on and into (Abyss's glass crates on B, glass floors); doors that
    are open in the game stay walk-through.
  - Replays no longer change a built map: the axes are checked with the callouts only, and where replays put the
    feet is measured when a replay is shown.
- The maps are built again once by themselves (a few seconds to a minute each; `nexus build-game` to do it now).
- The drills (aim on maps) walk on the same floors.

## 4.52.1
Security fixes from GitHub's code scanning (CodeQL). Nothing changes in how Nexus is used.
- **Paths from outside data**: one helper (`nexus/safepath.py`) joins a folder and a name and refuses anything that
  would end up outside the folder (`..`, absolute names, links pointing out).
  - The web app loads matches by **match ID only**. Before, a "match" ending in `.json` that existed as a file was
    read before the ID was checked (the web routes checked IDs first, but the loader itself didn't). Loading a saved
    match file is now the command line's own path (`load_match_from_file`, `CoachRequest.match_file`).
  - The HenrikDev client checks a match ID before it becomes a cache file name; a player's folder is always a number.
  - Translations are looked up by language code, never by building a file name from the request.
  - **Recordings folder** (admin, Users): the error no longer shows the path back, and with `NEXUS_VOD_ROOTS` set
    (folders separated by `:`) only folders inside those can be chosen.
- **Pages built from data**: the review evening, the roster drafts and the strat board escape every value they put
  into HTML (numbers from the server too), and only load icons and scripts from this site (never `javascript:` or
  another host). The strat board's element helper sets text by default; HTML only where the page builds it itself,
  and it drops `on…` attributes and `javascript:` links. Every copy of the escaping helper also escapes `'`.
- **Lineup links**: only youtube.com, www./m./music.youtube.com count as YouTube (`evilyoutube.com` doesn't).
- **Redirects**: "back to" targets from forms go through one check (pages of this site only); after saving, a page
  sends you back to itself built from its route instead of the request's URL.
- The review evening loads the playback script from its own known address, not from the page's data.
- **Error messages**: clips, Discord posts, the settings tests and the player order give fixed messages; the
  details go to the server log instead of the page.
- Roster drafts: no script error on a team without players yet.

## 4.52.0
- **Practice › Aim on maps: general drills on the real spots.** Four new tabs next to "Your deaths". The spots come
  from the fights in all replays of a map (up to the last 60): where defenders and attackers were, where attackers
  came from and the way they walked in. Pick a map, then a spot on the plan or in the list (the most fought-over
  first, with how often defenders won and your best), set the options and play.
  - **Hold an angle**: you stand where defenders hold, looking where the attackers come from. Enemies (random agents,
    animated, with rifles) peek from the real corner: **wide swing, jiggle peek, crouch peek, jump peek, two at
    once** (pick any). Kill each before he has you for his reaction time: Easy 0.9 s, Medium 0.6, Hard 0.42, Pro
    0.3. The result shows your time per kind of peek.
  - **Attacking: you peek**: you move, with Valorant's speeds (run 6.75 m/s, walk, crouch) and stopping, through the
    real map (walls, stairs). Up to three defenders on the places they held, each seeing ahead of him. Shots while
    moving go wide; a meter shows when you're still enough to be accurate, and the result how many of your shots
    were stopped and how fast you stopped (counter-strafing).
  - **Tracking**: an enemy strafes left and right (ADAD) where the fights happen, as far as the floor and your view
    go; how fast and how often he turns by difficulty. Stay on his head for 30 s: % on his head, % on him at all,
    second by second.
  - **Clear a site**: walk the attackers' most used route onto a site (drawn on the minimap). Each hiding place
    defenders used is checked the moment it opens: was your crosshair on it at head height (within 7°)? Two of them
    have an enemy. Score: crosshair placement in %. Hiding places you can see from the start don't count; you start
    where the route still hides the site.
  - Where you stand is checked against the map's walls: holding, you stand where the corner can be seen (a step out
    from behind a box if need be); attacking, you start on the attackers' route out of the defenders' sight.
  - Your gun, difficulty and reps per drill; your runs and best are kept per spot like the death drills.
- **Your keys**: moving (W A S D), walk (Shift) and crouch (C, not Ctrl: outside full screen Ctrl+W would close the
  tab) for the moving drills.
- The drills of each match are worked out once more in the background (they now keep the match's fights too).
- The 3D map's options (radar, callouts) aren't changed by the drills any more.
- German texts.

## 4.51.0
- **Practice › Aim on maps: your deaths as drills.** Every death in a match with a replay file, on a map built from
  the game's files, can be played again as an aim drill. You stand where you died, looking where you looked; your
  killer comes out of the same spot on his real path from the replay, as his agent (animated) with his gun, and the
  round's smokes and walls are where they were (smokes hide him, flashes that popped in your view blind you).
  - Kill him before **his time**: how long he had you in view before he killed you (the Combat Report's "who saw
    whom first"). Your time counts from the moment he could be seen. 10 reps by default (5 or 20), then the result:
    how often you beat him, your best and median time, every rep, where your first shots went (head, body, legs),
    how far off him your crosshair was when he appeared (and in the match), and your sessions on this spot.
  - Like Valorant: your sens and DPI from the aim trainer (0.07° per count × sens, 103° wide view, raw mouse input),
    the gun you had in that round with its real magazine, fire rate, reload and damage, zoom when aiming down
    sights. Hits count on the agent's skeleton (head, body and arms, legs), so a running or crouching enemy is hit
    where he's drawn; walls stop shots. "Count only headshots" (on by default) or real damage (150 HP).
  - **Watch how he did it** (P): his peek, slowed down. Options: the enemy's speed (0.75× to 1.25×), reps.
  - The list: one card per spot (the same angle killing you again shows as ×2, ×3) with his time, who saw whom
    first, your best; filters for the map, the last 10/30 matches or all replays, "only where he saw me first",
    and **Play them in a row**. The drills of new matches are worked out in the background (a few seconds each).
- **Your own keys**: shoot, reload, aim down sights, restart the drill, next rep, watch, full screen: any key, mouse
  button (4, 5) or the wheel, two per action, saved with your account (the same on every PC and in the Nexus app).
  A key on two actions is marked. Esc always stops. Defaults: Mouse 1, R, Mouse 2, Backspace, Space, P, F.
- The replay viewer and the drills share how players move (`static/motion.js`).
- German texts.

## 4.50.2
- **3D maps from the game's files: doors that are open in the game don't look closed any more.** The layouts have
  every door in its closed place, but most are open when a round starts (Ascent's two mechanical doors, Sunset's,
  Breeze's and Fracture's, Bind's teleporter doors, Abyss's breakable ones), so players walked through solid doors.
  A door standing in a walkable passage (the game's navigation mesh runs through it and on both sides) is now drawn
  like glass, faint, so you still see where it is, and it doesn't block the line of sight. The maps are built again
  after the update.

## 4.50.1
- **Pistols are held like in the game**: out in front with both hands. Every gun used the rifle pose, so a Classic
  or a Sheriff sat in the right hand at the chest while the left hand held nothing. The game's own pistol pose is
  used when it's in the export (`TP_Core_BasePistol_S0_IdlePose`, in an agent's folder); without it the pose is made
  from the rifle pose (the right arm stretched out to the left hand). The animations are built again after the
  update (`nexus build-game --data …`).

## 4.50.0
- **The agents move like in the game.** The replay viewer plays the game's own third-person animations on every
  agent: standing, walking and running in eight directions (blended, following where the player looks), crouching,
  in the air, and a death animation, away from the killer. **The bodies stay where they fell** until the round is
  over (the X on the floor gives way to the body; the radar keeps it).
- **Guns in their hands**: each player holds the gun he bought that round, and the one he killed with when he picked
  up another. The default skin of every gun, from the game's files.
- **The agents' portraits on top**, like in the game: your team left, the enemy right, a coloured bar per team, the
  dead greyed out and struck through. The same portrait in the player card.
- **P** plays and pauses in both camera modes. In the free camera **Space** flies up and **Ctrl** down (E/Q still
  work); in the player view Space still plays. In full screen the page keeps Ctrl+W & co. for itself (Chrome, Edge);
  outside full screen the browser closes the tab on Ctrl+W, so use Q there or switch to full screen.
- To get them: export `Characters/_Core` with its animations and `Equippables/Guns` too and copy them into
  `data/game/` (README › 3D maps from the game's files), then `nexus build-game --data …` and restart.
- German texts.

## 4.49.0
- **The replay viewer works like the game's own replays.** The view fills the page; the teams' agents (dead ones
  grey), the score and the round clock on top; the timeline and the controls below.
  - Two camera modes, switched with **V**: **Player** (through a player's eyes: `1`–`0` or his portrait picks him,
    a click on the view the next one, a right click or the mouse's back button the previous one) and **Free
    camera** (`WASD`, `E`/`Q` up and down, `Shift` faster, drag to look, the wheel flies forward).
  - **Space** plays and pauses (it used to make the camera jump), `←` `→` 5 s, `,` `.` rounds, `[` `]` speed from
    0.1× to 8×, **T** hides the controls, **N** opens the Combat Report.
  - The timeline: the rounds (won, lost, the side swap), and for the round kills ◆, deaths ▮, ultimates ★ and the
    spike; a click jumps 3 s before it.
  - No more "click to fly": the replay doesn't take over the mouse or the keyboard's walking keys any more.
- **Combat Report** (N), a drawer on the right: the round's kills with callouts and who saw whom first, *Your
  deaths* (the match's summary and this round's deaths, each with **Show the sightline**: the replay stops where
  your killer first had you, and the line between you two is drawn, red when it's clear), the utility check, and
  the team's comments.
- *See through walls* is now **Outlines**, as in the game.
- **3D maps from the game's files: walls with a window are walls.** A mesh counted as glass when any of its
  materials was glass, so whole buildings and boxes with a pane (Sunset's Elbow, among others) were drawn
  see-through and didn't block line of sight. Now only the glass faces are glass. The maps are built again after the
  update (or `nexus build-game --data …`).
- German texts.

## 4.48.2
- 3D maps from the game's files: **no more spiky shards**. Detailed objects were simplified too hard (some to 2 % of
  their triangles), which turned them into big slanted triangles; now every object keeps at least a third of its
  triangles and small ones aren't touched. The maps are a bit heavier (about 5–6 MB to download, the browser keeps
  them).
- The dark lids over closed-off blocks are only drawn from above: from below or the side they used to float in the
  air as dark plates.
- The maps are built again by themselves after the update (or `nexus build-game --data …`).

## 4.48.1
- 3D maps from the game's files: **no more holes in the floors** and no more slanted walls. The map used to be
  simplified as a whole, which tore gaps where separate pieces meet; now each object is simplified on its own, and
  big pieces (floors, walls, buildings) not at all.
- With the roofs cut away, the closed-off blocks (buildings, the space behind walls) used to be open to the sky;
  they now get a dark lid at the cut, like the blocks on the minimap.
- The maps are built again by themselves after the update (a minute or two in the background, or
  `nexus build-game --data …`).

## 4.48.0
- **3D maps from the game's files**: with VALORANT's map files exported with FModel (USD) on the server
  (`data/game/`, README › 3D maps from the game's files), the 3D maps are the real ones: every wall, floor, ramp and box
  at its real size, merged and simplified, in one colour. Plants, cables, lamps, decals, the vista around the map and
  invisible volumes are left out. *Floor* › *Height* colours by height, *Map areas* by the game's callout zones; roofs
  are cut away so the view from above shows the floors (*Roofs* shows them). Walking uses the game's navigation mesh.
  Maps without files stay rebuilt from the replays.
- Built in the background (`data/maps3d/*.game.*`) or with `nexus build-game --data …`; built again when the files
  change and once when a map's first replays arrive: they check which way round the export's axes are (FModel mirrors
  the world) and measure how high above the floor the replays put players.
- **Agents in the replay viewer**: every player is his agent's real model, in the team's colour, turned the way he
  looks. Walls hide players and their names; *See through walls* shows them again (hidden parts faint). The skeleton
  and skin weights are kept, so animations can come later without converting again.
- **Callouts**: kills name the game's own callout zone where the victim died (and the killer stood).
- **Line of sight and the death review**: from the map's walls, per kill: who saw whom first (in the field of view
  with a clear line to head or body) and by how much, how many enemies had a line to the victim just before he died,
  whether he ever had his killer in view. Shown under each kill in the round's list; *Your deaths* on the replay page
  sums it up for the match with the callouts you died at most.
- New dependency: fast-simplification (simplifies the maps; without it a coarser method is used).
- German texts.

## 4.47.1
- Fixed a test that still expected the old replay text without Custom games (the tests on GitHub failed for 4.47.0;
  Nexus itself was fine).

## 4.47.0
- **Custom games**: replays of Custom games work like any other replay: upload them (or let the Nexus app send them),
  watch them in 3D with the utility check and the team review, and coach them. The match details (names, teams,
  rounds, kills) are loaded from HenrikDev by match id, right after the upload, when the replay is opened, and every
  few minutes for older files; a match HenrikDev doesn't know yet is tried again after 6 hours.
- *Replay files* has a new list, **Custom games and other replays**: replays of matches that aren't in your match
  list (Customs, teammates' matches) with map, mode, date and score, *Watch in 3D*, and *Coach this match* when you
  played in it. Customs still don't count in your stats.
- After an upload the result says which match it was (e.g. *Custom Game: Ascent*) and links straight to the 3D view.
- German texts.

## 4.46.0
- **Smokes are 3D**: real balls of smoke in the 3D scene, cloudy, lit from above, with a soft edge, in the agent's
  colour (Miks green, Clove pink-white, Omen purple, Viper green, Astra violet, Harbor blue, Brimstone orange …).
  Walls hide them like everything else in the map, and inside one you see fog. Mollies and slows are discs on the
  floor, walls stand as columns, recon and traps are small balls, all hidden by walls too.
- **The map in one colour**, with a switch under the map (*Floor*): one colour, **measured · guessed** (floors the
  replays measured vs. filled in from the minimap) or the map areas (sites, mid, attacker and defender side) as before.
  Both on Practice › 3D maps and in the replay viewer; the choice is remembered.
- German texts.

## 4.45.0
- **3D maps are complete**: where no replay has been, the minimap's layout fills in the floor (walkable = the light
  parts of the minimap, worked out per image; boxes and walls stay solid) at the height of the nearest floor a replay
  knows. Every map can be opened now, flat until a replay of it is on the server; replays make the heights exact.
  Shared by Practice › 3D maps and the replay viewer.
- **Utility in the replay viewer**: smokes are balls of smoke (the same from every side), mollies and slows lie on the
  ground in perspective, walls stand as columns, recon and traps are markers. Effects that exist for less than about a
  second (an ability's targeting, like the violet circle when placing Miks' smokes) aren't shown.
- German texts.

## 4.44.0
- **Replay in 3D** (*Watch in 3D* on a match's page and on *Replay files*): the match's replay inside the rebuilt 3D
  map, round by round. Every player with agent, name and view direction; kills, the spike, smokes, walls, mollies and
  recon while they're up. From above (zoomable), through one player's eyes (click him), or flying freely (click the
  map). Play, pause, 0.5× to 4×, ±5 s and round keys, kill feed you can click to jump.
- **Team review**: comments at a moment of a round, kept per match for everyone in the team who can open it; rounds
  with comments are marked. You can delete your own.
- **Utility check** (same page): per player casts per key (C, Q, E, X), rounds with utility, deaths without having
  used any ability that round, and when the first ability of a round comes (attack and defense). The replay numbers
  its ability slots without saying which key is which; Nexus works that out from the match data's totals and, when
  they don't fit, shows the match data's numbers instead of guessing.
- **Nexus app sends every replay**: all files in the Demos folder (also the ones from before the app was set up),
  any mode. A replay of a patch vrfkit can't read yet counts as sent (the server keeps it); one that failed is tried
  again after 3 days. (*Opponents › Replay scouting* already covers opponent prep from replays.)
- The match page no longer says that only Competitive and Premier have replays.
- German texts.

## 4.43.2
- vrfkit looks for a new version every 3 hours instead of once a day (`deploy/nexus-vrfkit-update.timer`), so a
  new patch's replays are readable sooner. A check that finds nothing new is one quick look at GitHub.

## 4.43.1
- `nexus vrfkit-update` (the daily vrfkit update) stopped at once with "No module named 'nexus.store'": wrong
  import. Fixed, with a test that runs the command itself.

## 4.43.0
- **vrfkit updates itself**: `nexus vrfkit-update`, run once a day by a systemd timer
  (`deploy/nexus-vrfkit-update.timer`, install in the README). When vrfkit has a new version it's built in a separate
  folder and tested on the newest replay kept on the server; only if that works does it replace the old one (kept as
  `vrfkit.prev`, `--rollback` goes back). The result shows on the Server page and the Replay files page.
- **Replays of a brand-new patch are kept**: when vrfkit can't read a replay's patch yet ("unsupported replay
  branch"), the upload stays on the server (*Replay files › Waiting for vrfkit*) and is read by itself within
  5 minutes of vrfkit being updated, instead of being refused. Tried once per vrfkit version.
- Replay stats of a match are worked out again when its replay was read again (4.42.1's re-read now reaches the
  stats pages and the utility numbers).
- German texts.

## 4.42.1
- **Replay upload "Error 500" fixed**: some replays have an ability effect (a smoke, a wall …) still active when the
  recording ends; it has no end time, and sorting the effects crashed the import. Those replays now import.
- **Ability casts read again**: newer vrfkit versions store some text columns in a compressed form the cast filter
  couldn't handle ("ability casts not read" in the log), so every replay came in without ability casts (utility
  timing). Fixed; the replay files already on the server are read again once, in the background, after the update.
- An unexpected problem while reading a replay now says so in a sentence on the upload page instead of "Error 500";
  the details are in the server log.

## 4.42.0
- Player overview: every playstyle label is shown again (no "+1"); they wrap onto a second line when needed, and the
  labels have their own row shared by all cards, so the playstyle bars below still start on the same line in every
  card.

## 4.41.0
- **Player overview easier to compare**: the lineup cards now line up section by section, every *Agent roles*,
  *Playstyle*, *Thrives in* … starts on the same line in every card of a row, whatever is above it. The agent-role
  legend always shows all four roles in the same places (0 % faded), the playstyle chips fit on one line (two, then
  "+N" with the rest on hover), *Struggles in* and *Best maps* are always there ("nothing stands out yet"), name and
  numbers each on one line, and the playstyle bars all have the same length.
- German texts.

## 4.40.0
- **Replay files page** (*Performance › Matches › Replay files*, or *Upload replays* on the matches page): upload
  replay files of any match without starting a coaching run. Several at once (pick them or drag them in), one after
  another with progress; each says whether it's one of your matches (and which map) or another match (kept for that
  one). Teammates can upload for a shared player too. The page lists your matches that have a replay (with *Coach this
  match*) and your last 15 matches without one, so you see what's still worth uploading before the next patch
  deletes it. It warns when the server can't read replays (vrfkit missing).
- 3D maps without replays link straight to it; Ctrl+K finds it.
- German texts.

## 4.39.0
- **Does training help?** (*Practice › Aim › Aim insights*): each trainer skill next to the match number it should
  move: one taps and micro-adjusting → headshots, flicks, peeks and reaction → first duels won, target switching →
  kills per round, tracking → K/D. Week by week for the last 12 weeks: weeks you trained the skill (3+ rounds) against
  weeks without it, and whether the rating and the match number go up and down together. Until there are enough weeks
  (3 trained and 2 without, both with games; 5 weeks for "together") it says how many are still missing, and it never
  claims more than the numbers show.
- **Faster pages**: pages, data and scripts go out gzipped (the aim trainer page: 240 KB → 31 KB, its script 106 KB →
  33 KB), and scripts and styles of a version are cached by the browser instead of being checked on every page.
- **3D maps on the phone**: left thumb moves, right thumb looks around, a jump button; smaller radar on small screens.
  A map is now rebuilt in the background (every 5 minutes) when its replays change, so the page doesn't wait, and the
  rebuild itself is faster.
- Mobile: the scrims page showed its cards as a dark layer over the page on phones (fixed); tabs wrap onto a second
  line on small screens instead of hiding off the edge.
- German texts.

## 4.38.0
- **Fewer menu entries, grouped by topic.** The sidebar now lists topics, the pages of a topic are tabs at the top of
  the page: *Match day* (This week, Opponents), *Strategy* (Comps, Plans & strats), *Performance* (Matches, Stats),
  *Practice* (Today, Aim, Game sense, Ask the coach), *Team practice* (Practice, Review: review evening, recordings,
  scrims) and *Roster & setup* (Team, Player & playbook). Tabs you can't open (team settings for a non-owner) aren't
  shown. The player picker keeps you on the same page for the other player.
- **Today** (*Practice › Today*): what to practise today, in order: the warm-up (marked done once you played it),
  map prep for this week's Premier map of each of your teams, the skill to train next (20 or 10 minutes), waiting quiz
  questions, your focus of the week, this week's numbers, and links to the other tools.
- Ctrl+K also finds Today, the aim trainer, aim insights, mouse & monitor, callouts, 3D maps, sound, check-in, scrims,
  recordings and the aim board.
- German texts.

## 4.37.0
- **This week in the aim trainer** (Aim page): runs, minutes and days this week, every skill rating with its change
  since last week, new bests, and what to train next (a skill that went down, else your weakest) with a button that
  opens a 20-minute session of it.
- **Aim board** (*Team › Practice › Aim board*): everyone's skill ratings side by side with the change since last week
  and this week's training, and a **weekly challenge**: one scenario for the whole team (the owner picks it, a team
  sandbox scenario too, or it rotates by itself) with a leaderboard of everyone's best normal round this week.
  *Play it* opens it in your trainer.
- The aim board is posted to Discord with the weekly focus (same day and hour), or by hand from the board.
- German texts.

## 4.36.0
- **The warm-up follows your weakest skill**: still three 30 s rounds, grid flicks first, then the two easiest
  scenarios of the skill with your lowest rating (once two skills have a rating; until then grid, head-line and micro
  taps). The warm-up card says which skill.
- **Map prep** (trainer page): about 10 minutes for one map: one taps to warm up, every spot of that map from *Map
  angles* (up to four, 60 s each), a round of your weakest skill, and a button to the callouts quiz of the map at the
  end. The match screen links to it with the week's map, next to the warm-up.
- The match screen's warm-up card now has *Open the trainer* when your warm-up is the Nexus trainer.
- German texts.

## 4.35.0
- **3D maps** (*Practice › 3D maps*), first step: a map rebuilt from the replay files on the server. Every spot a player
  stood on is floor at that height (also a second floor above, like Heaven over Market), the gaps between paths close
  together are filled, everything else is a wall. Rebuilt again when new replays of the map come in.
- Walk around it: WASD, Shift to walk, Ctrl to crouch, Space to jump, F to fly, your Valorant sensitivity for the
  mouse. Steps and ramps are walked up, walls and boxes block you.
- Radar in the corner (R) and callout names in the world (C), both switched on and off and remembered; colours per area
  of the map (sites, mid, attacker and defender side) from a palette per map.
- With one or two replays a map is incomplete: corners nobody walked into are missing, and walls stand where nobody
  went. It gets better with every replay. The rebuild is tuned on test data so far and will be tuned on real replays.
- German texts.

## 4.34.0
- **Plays as** (Team settings › Teammates with access): the owner links a teammate's account to their player, so they
  can edit their own pool on the comp sheet even when their in-game name doesn't match the Riot ID.
- The comp sheet tells a teammate who isn't linked yet how to get linked, instead of just not showing *Edit*.
- Replay files: Nexus now keeps 10 positions per second per player from new uploads (was 4), for the 3D map rebuild
  coming next. Corrected: replays exist for Unrated, Competitive, Swiftplay and Premier, not only Competitive and
  Premier (Nexus never filtered by mode, only the texts were wrong).
- German texts.

## 4.33.0
- **Sandbox** (bottom of the aim trainer page): make your own scenarios from the trainer's 14 building blocks (flicks,
  targets that vanish, several on a wall, spider, bursts, moving targets, pop-ups, one taps, strafe tracking, path
  tracking, around you, switch tracking, peeks, hold the angle). Sliders and switches for every setting, *Try it*
  before saving, save for yourself or a team, change or remove your own (the team owner can remove the team's).
- Share a scenario as a code (`NX1-…`); pasting one adds the same scenario. Only settings are stored, never code, and
  the server checks every value against its range.
- Your scenarios keep scores like the built-in ones, and tagged with a skill they join that skill's sessions (at their
  difficulty) and its rating.
- German texts.

## 4.32.0
- **Train one skill** (aim trainer): pick tracking, snappy flicks, one taps, micro-adjusting, target switching,
  reaction or peeks and angles, and 10, 20 or 30 minutes. A session walks up that skill's ladder of scenarios (easy to
  hard) from the first one you aren't steady at yet, two 40 s rounds each, after a warm-up round.
- **Adaptive rounds**: after every round of a session the next one gets harder (targets 8% smaller, 7% faster) when it
  went well, easier when it didn't; the results screen says which. These rounds don't count for your bests.
- **Skill ratings** (0–100): per skill from your last 12 runs of its scenarios (accuracy, time on target, speed, how
  hard the scenario and the round were), with a chart by day. They compare you with yourself.
- **One taps**: 7 new scenarios where only the first shot counts, a miss and the target is gone: heads at head
  height near, far and close, three at once, quick ones, peeks from cover, and the doorway with an enemy model.
  108 scenarios in all.
- German texts.

## 4.31.0
- **VOD review**: watch a match recording together. *Review the recording together* on a report with a recording,
  or *Team › Practice › Recordings* for all of the team's recordings (with how many comments each has). Pause, draw
  on the frame (pen, arrow, circle, five colours), comment at that moment; each drawing shows at its time in the
  video. The timeline marks the rounds (won or lost, from the report) and the comments; jump to a round, slow down
  to 0.25×, step frame by frame. Teammates' new comments come in while you watch.
- Everyone in a team with that player can watch and comment (the recording too, not the rest of the report);
  whoever wrote a comment and the report's owner can remove it.
- German texts.

## 4.30.0
- **Scrims** (*Team › Practice › Scrims*): the team's scrim log. Per scrim: date, opponent, map, score, the side you
  started on and the first half (optional), what went well and what didn't, in words and as topics (retakes, trades,
  pistol rounds, comms and more). Over all scrims: won–lost, rounds won, the last ten results, per map and per
  opponent, rounds won per side, and *What the scrims show*: the topics that keep coming up as a problem or keep
  working, the best and worst map, the weaker side. Filter by map or opponent.
- Everyone in the team adds scrims; whoever wrote one and the team owner can change or remove it.
- German texts.

## 4.29.0
- **Sound** (*Practice › Sound*): hear where a sound comes from (headphones). Footsteps, a reload or a beep play once
  from somewhere around you, in 3D (the browser's HRTF panner); click the direction on a radar. Modes: *Direction*,
  *Distance* (also near or far) and *Height* (also above, same floor or below). 15 sounds a round, the closer the more
  points. Shows how far off you are on average, front/back mix-ups, and a wheel of how far off you are by direction.
  *Test the sound* checks left and right.
- The sounds are made in the browser, not Valorant's: what's trained is hearing the direction.
- German texts.

## 4.28.0
- **Map angles** in the aim trainer (above the library, and as a scenario in *Duels*): pick a map and where you stand
  (hold a site facing its main, or take it from main facing the site). Enemy models peek from behind cover at the
  callouts in front of you, at their real direction and distance on the map; the callout's name shows when one
  appears. Only headshots kill. The maps you play most come first.
- The map data has callout positions but no walls or heights, so every enemy is at your height and each spot gets a
  piece of cover.
- German texts.

## 4.27.0
- **Callouts** (*Practice › Callouts*): a quiz on the minimap. *Learn* shows every callout of a map, *Find it* names
  one and you click where it is, *Name it* lights up a spot and you pick its name from four nearby ones (keys 1–4).
  12 questions a round, faster answers score more, the callouts you get wrong come up more often. Per map: how many
  you know, best scores per mode, the ones you miss most. The maps you play most come first.
- German texts.

## 4.26.0
- **KovaaK's is gone from the web pages**: no KovaaK's page, no KovaaK's routines in the Aim library or warm-up, no
  KovaaK's share codes in *Add a routine*, no KovaaK's question in *Ask the coach* (and the coach no longer gets your
  KovaaK's scores), no KovaaK's in Settings, Account and This PC. If your warm-up was a KovaaK's one, it falls back
  to the Nexus trainer warm-up (if you've played the trainer, or have no warm-up routine of your own).
- Nothing is deleted: the code, your imported scores and saved share codes stay, and the desktop app's endpoints still
  work. One switch brings it all back: `WEB = True` in `nexus/stats/kovaaks.py`.
- German texts.

## 4.25.0
- **KovaaK's has its own page** (*Aim › KovaaK's*): the coach's playlists, community share codes, your imported scores
  and the scenarios the coach picks from moved off the Aim page. The Aim page is now the warm-up, what your matches
  show, the routines and the library; one card at the bottom opens KovaaK's (with how many runs you imported).
  Everything works as before: downloads, imports, the desktop app, KovaaK's runs as warm-up days.

## 4.24.0
- **57 more aim trainer scenarios, 100 in all**, modelled on the drill types KovaaK's and Aim Lab are known for
  (our own versions, names and texts), in two new groups and the old ones:
  - Moving targets: bouncing targets (normal, fast, close, tiny), a target that jinks, targets that hop up and fall,
    a moving target that respawns (near and far), strafing targets and strafing heads, a horde walking at you
    (normal and fast), shrinking targets.
  - Switch tracking: three moving targets, each goes down after a moment of fire on it; also fast, evasive (they
    dodge while you're on them), wide, small and floating.
  - Flicks: behind you (up to 175°), spider 180, speed and precision versions, low and high flicks.
  - Switching and precision: grid speed / precision, six shot precision, wide walls with three and five targets,
    heads at any range, triple tap, burst flicks (a group of three or four, far from the last group: wide and micro).
  - Reflex: side vision (far to the sides), pop-ups (several at once), friend or foe (don't shoot the blue ones, they
    cost points; also fast), reflex close and at head height.
  - Tracking: line tracing, arcs, stars (also micro), circles (also small), blink tracking (the target jumps away),
    tracking above and below you, long strafes (also close), zig-zag, fast around you.
- Results show the blue targets you hit (friend or foe) and the targets you took down (switch tracking).
- German texts.

## 4.23.0
- **Aim trainer scenario library**: 32 new scenarios, 43 in all, in six groups with a difficulty each:
  - Flicks: mid-range, wide (50–70°), vertical, tiny, spider (out and back to the middle).
  - Switching: six shot, head-line switching, close switching (up to 65° apart), tiny switching, double tap
    (two hits per target).
  - Reflex: targets that vanish after about a second, shorter after every hit (normal, small, wide).
  - Precision: pinpoint, far head-line, far spider, micro spider.
  - Duels: far and fast peeks; the doorway with an enemy model as close angle, long angle, jiggle peeks, wide swings
    and runners (headshots only).
  - Tracking: smooth, fast strafes, small target, jumping strafes, crouch spam, around you (a target circling you),
    air tracking, up and down.
- The scenario list is a library: filter by group and difficulty, search (in English and German), "not tried yet".
- The daily training picks from the whole library by what your matches show.
- German texts.

## 4.22.0
- **Quiz on the playback**: each question shows the round on the minimap up to the moment it asks about, locked
  there (no later kills on the bar or in the list, no round length) until you answer; then it plays on so you see
  what happened. If your coaching report of that match commented on the round, the coach's summary, mistakes and
  better option are shown with a link to the report. Questions from older quizzes work as before, without the map.
- **Who should learn what** (*Strategy › Comp sheet*): the agents your maps need (ideal comp, or picked by a third
  of the teams in your lobbies) that nobody has in their pool, the thin roles, and per player the one or two of
  those agents that fit best (how much they play the role, their ACS on it against players of their rank on the
  same agents; a player who alone covers another role stays there). *＋ Add to pool* adds it to the player's pool.
- The review evening's playback builder is shared with the quiz.
- German texts.

## 4.21.0
- **Team economy** (*Strategy › Economy*): the team's buys in your matches together, next to the teams in the same
  lobbies (same maps, patch and ranks): round win rate per buy and per matchup, forces that were lost and left you
  broke the next round, split buys (2+ on rifles while 2+ save), the round after a won pistol, who bought while the
  team saved (and the other way round) and how many rounds per match are lost to buys. Plain lines on what stands
  out; the weekly focus coach gets the same numbers.
- **The opponent's replays on match day**: when a scouted Premier team is in your replay files (3+ of the same
  players), the opponent card on the *Match screen* and the team's scouting page show its habits on the map with a
  link to *Replay scouting* and *Write counter-plans*. The *Match-day brief* (page and Discord post) lists every team
  of your division you have replays of.
- Fixed: posting the match-day brief to Discord failed when only one side's round win rate was known.
- German texts (also the matchup descriptions on *Rounds & economy*).

## 4.20.0
- **Lineups from your replay files** (*Strategy › Lineups*): utility one of you threw from about the same spot
  (within 4 m) to about the same spot (within 3 m) three times or more shows as a suggestion, with a small map of
  the throw, where it lands, the usual time and who throws it. *＋ Add* puts it in the library (add a clip later).
  The replay extracts are worked out once more to know where each throw came from.
- **Notes in your coaching reports**: the report's playback has *✎ Note* too (only you see them), *⇢ Strat board*
  (into your team's strat book) and the new picture buttons. Older reports get them as well (the current playback
  is loaded into the report).
- **A moment as a picture**: *⤓ Picture* saves the playback as it's shown (zoom, utility, notes) as a PNG; *📷 Discord*
  posts it with the notes around that time, from a report to the team's clip channel and from a review evening to
  its review channel.
- German texts.

## 4.19.0
- **Counter-plans from replay scouting**: on *Replay scouting*, *Write counter-plans for <map>* gives the coach the
  team's habits from the replay files (setup and spots at 20 s, utility with place and time, plants) together with
  your numbers, comp and roles. It writes 3 game plans (2 attack, 1 defense) built to punish those habits, each
  saying which habit it uses. They show under *Game plans* as *Counter-plans against …* (replacing that map's
  plans; *Write plans* makes general ones again) and the Discord match prep names the opponent.
- **Goals from "You vs your rank"**: every number that's behind your rank (or, where you're there already, a rank
  higher) has a *＋ Goal* button. It sets a goal for the next 10 games on the Habits page, which checks itself
  against your games. New goal numbers for that: kills, deaths and assists per round.
- German texts for both.

## 4.18.0
- **You vs your rank** (*Stats & maps*): your ACS, kills / deaths / assists / damage per round, headshot share, KAST
  and opening duels against the other players of your rank in your own matches (within one division, by the rank
  shown in each match), and against the players a rank higher once there are enough of them. Clear differences in
  green / red plus a line on the biggest ones. Game rows are rebuilt once from the cache (row v7) to get everyone's
  numbers; the coach gets the comparison too.
- **Notes on the playback** (*Review evening*): pause, press *✎ Note*, draw on the map and write a line. Everyone
  sees it on the time bar and in the *Notes* list; the drawing shows around its time and the playback stops there
  (*stop at notes*, can be switched off). Your own notes can be deleted, the host can delete all.
- **⇢ Strat board** on the review evening's playback: this moment as a new board in the strat book, with everyone
  alive where they stand (both teams, with names), the utility that's up and the drawings.
- **Replay scouting** (*Match day › Replay scouting*): from the replay files of your matches, how a team you played
  sets up (e.g. "A 2 · Mid 1 · B 2" at 20 s), the spots it takes, the utility it throws (type, place, usual time) and
  where it plants, per map and side, on the map. Works for your own team too ("how readable are we"). A team met
  more than once (three or more of the same players) is put together.
- The review evening's minimap uses the replay file when there is one (all ten players' paths, placed utility).
- German texts for all of it.

## 4.17.0
- **When you play best** (*Progress*): your win rate by game in the session (games less than 75 minutes apart count
  as one session), after 0 / 1 / 2+ losses in a row, by time of day and by weekday, each bar green / red when it is
  5 points above / below your overall win rate, faded when it rests on few games. When a difference is clear the
  page says it in a sentence ("From the 4th game of a session the win rate drops from 56% to 41%: stopping after 3
  games is worth trying"). The coach gets the same numbers.
- **Who plays well together** (team *Player overview*): every pair of teammates with games, win rate, how often they
  traded each other and how often both died alone in the same round, plus the best and weakest pair, the pair that
  trades each other most and the one that splits up most. The weekly focus coach sees each player's pairs.
- German texts for both.

## 4.16.4
- **Rank over time stays current**: besides HenrikDev's stored rank history (long, but only updated when HenrikDev
  looks the account up, so it could lag days behind), every import now also reads the live history of the last
  ranked games. Both are merged, nothing is counted twice. The import log shows both ("recent rank", "rank
  history").
- The rank chart's labels no longer blow up on wide screens (normal font and size).

## 4.16.3
- **Placed utility in the round playback** (reports with a replay file): smokes (grey areas), slows and mollies /
  damage zones (coloured areas), walls, traps, recon bolts and drones (pulsing ring), orbs and flashes (ability
  icon), each at its spot for as long as it lasted, outlined in the owner's team colour; hover for who and which
  ability. From vrfkit's effect actors (class, spawn spot, open / close); a thrown projectile is placed where it
  last moved. Replays stored before are read again once; run the coaching again for older reports.

## 4.16.2
- **Utility in the round playback** (reports with a replay file): a ⚡ pulse where a player used an ability, small
  ticks under the time bar (your casts taller), "⚡ N" abilities so far next to each player, your own casts in
  *Round events*, and a *utility* switch to hide them. Buy-phase casts show at 0:00. Reports made before this
  update get it when the coaching is run again.

## 4.16.1
- **Replay files on the Server page** (*Server*, admins): how many matches have a replay file, their size, how many
  were uploaded in the last 7 and 30 days, the last upload, how many still have the .vrf, how many were lined up
  with the match data and how many have ability casts, replays per map, and whether vrfkit works. Their size is
  also listed under *Disk*.

## 4.16.0
- **Utility timing from replay files**: the ability casts in the replay (vrfkit's *AbilityCastsThisRound*) give
  *Utility before the first fight*, *Died without using utility* and *First ability* (median, attack / defense)
  on *Habits › From your replay files*, and the coaching run sees each round's casts. Replays stored before are
  read again once (needs the kept .vrf and vrfkit).
- **Check-in reminder on Discord**: a Premier review posted to Discord starts with "How did it go?" and a link to
  that match's check-in. Reviewed Premier matches show on the check-in page right away, before the next stats
  update.
- **Releases tag themselves**: merging a PR that raises the version tags exactly that commit and starts the
  Windows app build (`.github/workflows/release-tag.yml`); it refuses when the three version numbers differ. No
  more `git tag` by hand.

## 4.15.0
More accurate coaching: the coach knows how reliable each number is, sees more than the kill moments, and learns
whether its advice worked.
- **Replay-file numbers** (*Habits › From your replay files*): untradeable deaths (no teammate within 15 m then
  or in the next 3 s), retake arrival (got to the spike, after how many seconds), and setups: where each player
  stands 20 s into the round per map and side, with the win rate of each spot. Also given to the coach.
- **Recent games and the current patch count more**: half the weight every 45 days, older patches 60 %, stronger
  lobbies a bit more. Used by the comp maker (all modes) and the coach; shown on *Stats & maps › How much the
  numbers tell*.
- **Buy state and lobby strength**: rounds split into full buys, anti-eco and your own eco / force (round win
  rate, K/D), with a note when the K/D mostly comes from anti-ecos; games against stronger / similar / weaker
  lobbies. The buy states are part of *Thrives in / Struggles in*.
- **"Solid" or "early sign"** on every playstyle label and situation (*), and in the coach's data; the coach must
  quote the number behind each point and call early signs early signs.
- **Goals** (*Habits › Goals*): a number, a target and the next games, checked automatically after every game
  (reached / missed). Set by the weekly focus, by *Make it a goal* on a habit, or by hand. The coach sees the
  results and changes approach where a goal was missed.
- **Post-match check-in** (*Match day › Check-in*): who called, comms and mood (1–5), one line, in about 20
  seconds. From 3 votes, the IGL suggestion follows the team's answers instead of a guess. Used in Premier reviews,
  the weekly focus and *Ask the coach*.
- New habit: **Dying with utility unused** (deaths in rounds without any ability, from the match data).
- Rows are rebuilt from the cached matches at the next stats update (patch, lobby ranks, kills per round).

## 4.14.1
- **Comp sheet uses the space better.**
  - *Ideal composition*: a map with a comp is now one full-width row: the map with its source and buttons on the
    left, then a wide column per agent with the players who have it in their pool (green = high in the pool, red =
    low; long names are shortened, hover for the full name). Maps without a comp are small cards below and no longer
    stretch to the height of the others.
  - *Agent pool*: each column shows the top 8 agents, "+ N more" / *Show all agents* opens every list at once so
    the columns stay comparable. Long player names no longer push the column header out.

## 4.14.0
- **Follow our agent pools**: a new switch next to *Make comps with* (comps page), on the comp sheet and in the
  team settings. When it's on, the comps use each player's agent pool from the comp sheet in every mode (Map
  rules + your stats, Most comfortable, From the web, Your stats only), for drafts and the Discord prep too:
  - agents a player marked *won't play* are left out;
  - agents he ranked high get a bonus; in *Most comfortable* his own order counts instead of games played;
  - agents he added by hand can be picked even without games (no "new agent" penalty in *From the web*).
  Each pick says why, e.g. "#1 in Sam's agent pool". Off by default; the team owner switches it.

## 4.13.0
- **Comp sheet** (*Strategy › Comp sheet*): the team's agent pool and ideal comps on one page.
  - *Agent pool*: a column per player, best agent first and coloured green to red, made from the stats (most played,
    then win rate). Each player can reorder his own list, add agents and mark agents he won't play; the team owner
    can edit every list. *Back to the stats* resets a list.
  - *Ideal composition*: per map the comp web sources name most (searched with one click, also when the comps page
    uses another mode) or 5 agents set by hand. Under every agent: who has it in his pool and at which rank,
    "nobody" if no one does.
- **Fix: "From the web" said web search was off** although it is on (DuckDuckGo by default). The check looked at a
  setting that doesn't exist; it now uses *Settings › Web search*.
- **Explanations that open**: the labels in the player overview (playstyle, thrives / struggles, suggested role,
  IGL / Operator, table cells) show their explanation in a popup on hover, on keyboard focus and on tap (phones).
  Before, only a "?" cursor appeared and nothing came up.

## 4.12.0
- **Playstyle labels** in the player overview, independent of the team role: up to three of *Aggressive*,
  *Patient*, *Clutch player*, *Trader*, *Lone wolf*, *Survivor*, *Fragger*, *Playmaker*, *Brawler*,
  *Long-range duelist*, *Operator player*. Hover a label to see the numbers behind it.
- **Thrives in / struggles in** per player: opening duels, clutches, retakes, post-plants, close / mid / long-range
  duels, attack vs defense, fighting away from vs next to the team, trading teammates; compared with typical ranked
  values, with a minimum number of rounds and small samples pulled towards typical. In the full view too.
- Both come from the round data of the stored games; no model needed.

## 4.11.0
- **Player overview** (*Roster & setup › Player overview*): who plays what, at a glance. Per player the role (yours
  from *Roles*, else the suggestion) and IGL / Operator, the most played agents, the split over Duelist / Initiator /
  Controller / Sentinel, the playstyle (four bars, in words, closest pro) and the best maps. On top: which agent roles
  every starter plays regularly, roles nobody covers, two players with the same main. Two views: **Top 5 agents**
  (cards) and **All agents** (every agent and every map in a table, players side by side). Calculated from the games,
  no model needed.

## 4.10.1
- **Make comps right on the comps page** (Strategy › Comps): pick how the comps are made (Map rules + your stats,
  Most comfortable, From the web, Your stats only) and click *Make comps*; no trip to the team settings. With
  *From the web*, the selected map is searched right away if it hasn't been yet. Teammates see which mode is used;
  the team owner changes it.

## 4.10.0
- **Comp suggestions, four modes** (team settings): *Map rules + your stats* (default, as in 4.9), *Most comfortable*
  (every player on what he plays most, on that map first; win rates don't count), *From the web* (comps that web
  sources name for the map, handed to your players by their numbers, with the sources linked; *Search comps for
  <map>* / *All maps* on the comps page, needs Settings › Web search) and *Your stats only* (as before 4.9).
  Drafts and the Discord prep use the team's mode too.
- **"You are" is gone** from the comps page: you are the team player whose Riot ID is your in-game name (Account),
  linked by itself. Links set before stay.
- **Dropdowns readable in every style**: the open list of a select (e.g. the model picker) was see-through in the
  Neon and HUD styles, especially in the Windows app.
- Security (CodeQL): replay file paths only take a match id and must stay inside the replays folder; the vrfkit
  test no longer shows the system's error text (it goes to the server log).
- README: installing vrfkit without Docker needs a C compiler and linker (`build-essential`).

## 4.9.0
- **Replay files**: VALORANT's own replay of a match (`.vrf`, downloaded in the game's match history, Competitive and
  Premier) has every player's position for the whole round. Upload it on the match's coach page (*Replay file* card)
  or let the Nexus app send new ones by itself (*This PC › Replay files*). Nexus reads it with
  [vrfkit](https://github.com/yakisoba0728/vrfkit) and lines it up with the match data by the kills, so:
  - the round coaching gets where **both teams** really were, per 10 s (setups, stacks, rotations, timings), not only
    what your minimap showed;
  - the report's replay draws **all ten players' real paths** instead of estimating them between kills;
  - no recording is needed for that; a VOD still gives the jump buttons.
- **Switch back**: *Settings › Replay files › Positions* = *VOD minimap only* makes reports exactly as before.
  With *Replay file when there is one* (default), a match without a replay file, or with one that doesn't fit the
  match data, uses the VOD minimap as before. The report header says which positions were used.
- **vrfkit**: the Docker image builds it. Without Docker install it once (README, *Replay files*); *Settings › Replay
  files › Test* checks it. New dependency: `pyarrow` (`pip install -e .` installs it).
- **Team comps with map rules**: *Comp suggestions* in the team settings. *Map rules + your stats* (default) adds what
  the stats can't know: the role mixes that work on each map, the agents a map needs or rewards (a Viper wall on Breeze
  and Icebox, recon on Ascent, …), and for every comp a controller, at most two duelists, someone to flash corners and
  someone for information. Every rule that changed a comp is shown under it, and the picks say why. *Your stats only*
  makes comps exactly as before. Admins edit the rules under *Settings › Map rules for team comps*; a team's own map
  meta still wins.
- Nexus app for Windows 4.9.0: sends replay files from VALORANT's Demos folder (on by default; each file once, one the
  server can't read is not sent again).

## 4.8.0
- **Aim insights** (*Practice › Aim insights*, or *Aim insights* on the trainer page): every round in the aim trainer
  now measures how you aim, and the page shows what stands out over the last 30 days:
  - flicks per direction: slower to the left than to the right (or up than down), small corrections or big turns that
    take long, flying past targets or stopping short;
  - where missed shots land (above, below, left, right of the target);
  - tracking: on target while it moves left against right, behind or ahead of it, how long it takes to be back on it
    after a direction change;
  - duels: reaction to peeks from the left and the right, where your crosshair waited (below or above head height), body
    shots instead of headshots;
  - how much your scores jump around.
- Each finding says what was measured, gives tips for your **hand and grip** (pick right or left hand and palm, claw or
  fingertip on the page: a slow side toward the thumb needs more forearm, flying past with a fingertip grip needs a
  little palm contact, …) and links the scenarios to play (*Play …* opens the scenario in the trainer). What's already
  good is listed too.
- **Charts**: a skill profile (flick speed, accuracy, small fixes, tracking, reaction, crosshair placement,
  consistency), a wheel of flick speed per direction coloured by flying past or stopping short, a map of where missed
  shots land around the target, tracking left and right with a behind/ahead gauge, peeks per side with where your
  crosshair waited, flick time by size, and scores over time per scenario.
- **Focus training**: the scenarios for the top findings, two rounds each, on the insights page and as a third plan on
  the trainer page. Finishing it ticks it off on the Aim page like the warm-up and training.
- The coach (*Ask the coach*) knows the top findings, your strengths and your grip.
- Only rounds played from this version on carry the measurements; older scores stay as they are.

## 4.7.2
- **Availability: everyone sets only their own days**, the team owner too. And nobody has to pick who they are: Nexus
  finds your player by the in-game name you entered when signing up (or under *Account*, `Name#TAG`), or by an
  existing link to your player on the team page. Your row is at the top and marked *You*; the other rows can't be
  clicked. Without an in-game name, the page says where to set it.

## 4.7.1
- Sens finder chart: point at a dot to see that round: the sens, cm per 360° with your DPI, how good it was compared
  with that test's best, and the day and length of the test (tap on a phone). The dot nearest the pointer is picked,
  so dots close together can each be reached.

## 4.7.0
- **No more pauses in the sens test**: a new flick target was placed from where you aimed, and after a few low ones it
  could land in the floor, hidden, so you searched until the round moved on. Targets now always stay between floor and
  ceiling, every part of a round starts at your crosshair, and between rounds a line says which test is next. If the
  browser itself stands still (another program, a busy tab), the result says so, so it isn't taken for the trainer.
- **Crosshair inside the trainer**: *Crosshair* on the start, pause and result screens opens the settings next to the
  game, so you see your real crosshair while changing it (Valorant code in and out as before). Esc or *Done* closes it.
- **Sens finder in 5, 15 and 30 minutes.** 15 and 30 minutes play close flicks, far flicks, close, far and reactive
  tracking in every round and show which sens each part likes (flicks often like a little less than tracking). 30
  minutes: more sensitivities, the close ones three times, your own sens at the start, middle and end to measure tiring,
  and a minute's break halfway. Longer tests count more (15 min twice, 30 min three times). Tiring is now worked out
  from all rounds at your own sens.
- **New scenarios**, grouped into flicks, duels and tracking: *Close flicks* (big targets far to the side, an enemy next
  to you), *Far flicks* (small targets on a long angle), *Close tracking*, *Far tracking*, *Reactive tracking* (short
  ADAD strafes and sudden stops), and **Hold the angle**: you hold a doorway and an enemy model swings wide, jiggles or
  runs through from the left or the right. Only a headshot kills; body shots and enemies that got away are counted.
  Today's training can pick them too.

## 4.6.1
- **Aim trainer: fullscreen** while playing, on by default (a switch next to the sensitivity; F switches it while
  playing). In the Nexus app the whole window goes fullscreen.
- **Crosshair drawn on the screen's real pixels**: with Windows display scaling (e.g. 125%) the browser stretched it
  by a fraction of a pixel, which made the lines look smeared and uneven. It's also exactly the same on all four
  sides now (the right and bottom lines sat one pixel further out), in the game and in the preview.

## 4.6.0
- **Aim trainer** (*Practice › Aim trainer*): Nexus's own aim trainer in the browser and in the Nexus app. It plays
  like Valorant: your Valorant sensitivity, Valorant's field of view (103° at 16:9) and raw mouse input through
  pointer lock (Chrome, Edge and the Nexus app; other browsers say that Windows' acceleration applies). Five
  scenarios: grid flicks, head-line flicks, micro taps, peek reaction (enemies peek from behind cover) and strafe
  tracking. *Today's warm-up* is three short rounds; *today's training* picks the scenarios that fit what your matches
  show, the one furthest below your best first. Scores, best and trend per scenario, kept per player. Finishing a
  warm-up or training ticks it off on the Aim page, where both are new routines (*Open the trainer*).
- **Sens finder** (in the aim trainer), in two modes. *Quick* (about 5 minutes): one warm-up at your sens, then ten
  20-second rounds of a mixed test (flicks, micro corrections, tracking), five sensitivities from 70% to 130% of yours
  and five close around the best of those. *Thorough* (about 11 minutes, counts twice): two warm-ups, then 21 rounds of
  25 seconds, seven from 65% to 150%, six close values played twice each, and your own sens at the start and the end:
  how much worse the last one was shows how much you tired, and the rounds in between are corrected for it. Both
  blind and in random order. It measures how you hit: overshooting the target (too fast),
  stopping short (too slow), time to hit, accuracy and time on the moving target. A curve through the results gives the
  recommended sens and the range that works about as well, with cm per 360° and a chart. Tests of the last 90 days are
  combined (each scaled to its own day), and it says how sure it is (one quick test, or several days that agree). If the best
  was at the end of what was tested, the next test starts there. A change of more than about 10% comes as weekly steps.
- **Crosshair** (in the aim trainer): like Valorant's crosshair, in screen pixels: colour, outlines, centre dot, inner
  and outer lines (length, thickness, gap, opacity), with a preview. Paste your Valorant crosshair code to take it over,
  or copy yours as a code for Valorant. Kept per player.
- **Esc pauses properly**: during a round and during the countdown, with *Continue* (also Enter or Space), a short
  countdown back in, and the round goes on where it stopped. Esc no longer closes the trainer by accident, and when the
  browser needs a moment after Esc before it can lock the mouse again, *Continue* waits for it.
- In the sens finder's test the moving target now appears right at the crosshair and moving, with *Track it* and the
  target lighting up while you're on it (it looked like a pause before). Between rounds: 2 seconds instead of 3.
- **Mouse & monitor** (*Practice › Mouse & monitor*): the real DPI of your mouse (move it a known distance along a
  ruler, several tries averaged, compared with the DPI you set, with a hint when the browser's display scaling is the
  difference), the polling rate, the refresh rate your screen really shows (with a moving test square), and a button
  test that catches worn switches that double-click. Plus eDPI and cm per 360° with the DPI you set and the one
  measured. *Save* keeps the values for the trainer and the coach.
- *Ask the coach* knows the trainer scores and your mouse (sensitivity, measured DPI, cm per 360°, polling and screen
  rate).

## 4.5.0
- **valcoach is now Nexus.** The name in the app, the Python package (`nexus/`), the command (`nexus web`,
  `nexus --version`), the service (`deploy/nexus.service`), the Docker image and the environment variables
  (`NEXUS_BACKUP_ROOTS`, `NEXUS_MODEL`). What carries over by itself: `data/valcoach.db` is renamed to
  `data/nexus.db` at the first start (with its `-wal`/`-shm` files), backups named `valcoach-backup-…` still count
  for the list and how many are kept, the old `VALCOACH_*` variables still work, logins and the language cookie
  stay. Once on the server: `pip uninstall -y valcoach && pip install -e .`, then install `nexus.service` instead
  of `valcoach.service` (README › *Coming from valcoach*). The GitHub repository keeps its name for now.
- **Nexus for Windows instead of the companion app.** One app that shows Nexus in its own window (WebView2) with
  everything the website has, plus **This PC** in the menu, which only exists in the app: the player, a tile each
  for playlists, scores and Medal, the two folders, the switches, the activity, *Sync now*, updates and *Change
  server*. You log in in the window like on the website; the website then gives the app its own key for that PC
  (`POST /account/devices/pair`, with the session and the usual same-site check), so there's no second login. Tray
  icon, *Start with Windows*, the installer and the updates stay. Links to other websites open in the browser, and
  only Nexus's own pages can talk to the app.
- **From the companion app:** it updates to the new app by itself (each release has the installer a second time
  under its old name, `valcoach-companion-setup.exe`). The installer removes the old program file and shortcuts,
  the app takes over the settings, what was uploaded already, the device key and *Start with Windows*.
- *Account*: the section is now *Nexus app for Windows*; the coach page says *From the Nexus app*.

## 4.4.2
- **Companion app without the long scroll:** a sidebar with *Overview*, *KovaaK's*, *Medal* and *Settings*, one page
  at a time, in a wider window. *Overview* has the player, a tile each for playlists, scores and Medal (on, off or
  "check folder", with the last result; a click opens its page) and the activity. Status and *Sync now* stay at the
  bottom of the sidebar. Logged out, the app only shows a login card.

## 4.4.1
- **The installer is built however a release is made:** pushing a tag `vX.Y.Z`, publishing a release on GitHub's
  page (that didn't start the build before, so v4.4.0 had no installer at first), or *Actions › companion › Run
  workflow* with *release* set to a tag, which attaches the installer to that existing release afterwards.
- A test's fake GitHub check looked for `api.github.com` anywhere in the address (CodeQL warned); it checks the start
  of the address now. The app itself always checked the start.
- The test workflow only gets read access to the repository (CodeQL's advice for workflows).

## 4.4.0
- **Companion app: an installer instead of a loose .exe.** `valcoach-companion-setup.exe` installs it for your
  Windows user (no admin rights) into `%LOCALAPPDATA%\Programs\valcoach companion`, with a Start menu entry and an
  uninstaller under *Settings › Apps*; the downloaded installer can be deleted right away. Uninstalling also
  removes *Start with Windows*.
- **The companion app has valcoach's version** (this one is 4.4.0 too, after 1.1.0). Releases are the normal
  valcoach tags `vX.Y.Z`: pushing one builds the installer on Windows and attaches it to that release (the workflow
  refuses a tag that doesn't match the version, and a test checks that both version numbers agree). The
  `companion-v...` tags are gone.
- **Updates go through the installer:** the app downloads it to the temp folder, checks it against the SHA-256
  GitHub lists for the file and runs it silently; the app closes and starts again by itself.

## 4.3.1
- **Companion app 1.1.0:**
  - **Updates itself.** Once a day (and on *Check for updates*) it looks for a newer release on GitHub; *Update now*
    downloads it, checks it against the SHA-256 GitHub lists for the file, swaps it in and restarts. To publish a
    version: raise it in `companion/valcoach_companion/__init__.py`, merge, push the tag `companion-vX.Y.Z` (the
    workflow refuses a tag that doesn't match).
  - **New look:** dark, in valcoach's colours, with cards for account, KovaaK's, Medal, activity and the app,
    switches instead of checkboxes, a status in the header (up to date / working / logged out) and *Sync now* at
    the bottom. The .exe and the window have valcoach's diamond as icon.
  - The window and the background sync could save the settings at the same moment and lose a write; they take
    turns now.

## 4.3.0
- **Companion app for Windows** (new, in `companion/`): a small tray app for each player that every few minutes
  - puts the coach's KovaaK's warm-up and training playlists into KovaaK's Playlists folder (dated, once a day;
    the coach's own files older than a month are removed, nothing else is touched),
  - sends new KovaaK's scores from KovaaK's `stats` folder to the Aim page,
  - cuts your matches out of **Medal** session recordings and uploads them: Medal names a recording after its start
    to the millisecond, Riot's data has each match's start and length, so every match in an evening-long
    recording is found, however long you were in the menu. Cut without re-encoding, 90 s before and 60 s after the
    match; a recording whose length doesn't fit its times (Medal paused) is skipped instead of cut wrong.
  Each part can be switched off. Built as one .exe by GitHub Actions (push a tag `companion-v1.0.0`).
- **The coach page picks the companion app's clip** of a match by itself (*From the companion app*). Like any
  uploaded VOD it's deleted after the report; clips no report used are deleted after 14 days
  (`companion_keep_days`).
- **Account › Companion app**: the devices logged in to your account, each with *Log out*. The app logs in with
  username and password once and gets its own key for that PC (only its hash is stored; it only opens the app's
  `/api/companion/...` calls, and changing your password logs out every device). Logging in from the app counts
  toward the same lockout as the login page.
- The match list gives each match's length to the app (`length_s`).

## 4.2.2
- **Settings › Web search › Test shows each search on its own line** with its own ✓ or ✗ (before: one line with a
  green ✓ as soon as either search worked, even when the main one had failed).
- **DuckDuckGo's refusal is described correctly:** it often refuses searches that don't come from a browser, even the
  very first one, so it isn't about searching too much. The hint now recommends SearXNG as the main search and
  DuckDuckGo as the backup at most. valcoach doesn't try to get around DuckDuckGo's check.

## 4.2.1
From code reviews of 4.2:
- **Search the web for KovaaK's playlists runs in the background.** It reads up to six pages and used to keep one of
  the server's few web workers busy for up to a minute; now the page asks every few seconds until it's done.
- **Web pages are read from exactly the address that was checked.** Before, the check looked the name up and the
  download looked it up again, so a name that changes its answer in between (DNS rebinding) could have reached the
  LAN. HTTPS still checks the certificate for the name.
- Web search: the pages that get read are the best hit of *each* search (before: the first three hits of the first
  search), the search cache keeps at most 500 searches, and a model that writes no search queries is logged.
- Errors when the coach can't answer (*Ask the coach*, questions about a round) show valcoach's own messages
  (Ollama not reachable, no Claude key, budget used up ...); anything else shows a general message and the details
  go to the server log.
- `X-Forwarded-Host` only counts for the form check when the request comes from a reverse proxy on this machine or
  the local network.
- **The database uses SQLite's WAL mode**: pages keep loading while a job writes. Nothing to do: it switches on at
  the next start.
- Faster report parsing: kills are grouped by round once instead of searched for every round, and the deaths of a
  round are worked out once instead of up to four times.
- `knowledge/playbook.example.yaml` uses `teammate1` again, like the copy in the app.
- `werkzeug`, `markupsafe` and `urllib3` are listed as dependencies (valcoach imports them itself).
- New: `CONTRIBUTING.md` (setup, tests, what a pull request needs), `SECURITY.md` (how to report a problem
  privately, what valcoach protects), `.pre-commit-config.yaml` (ruff before every commit: `pre-commit install`).
- README: the overview is a diagram GitHub draws (Mermaid), with a table of contents below it.

## 4.2.0
- **Ask the coach** (*Practice › Ask the coach*): a chat with the coach about one player. It knows the player's recent
  form, agents, maps, habits, what their aim needs and their KovaaK's scores, and remembers the conversation (per user
  and player; *New conversation* starts over). Answers are written in the background, with the model picker like
  everywhere else.
- **Web search for the coach** (*Settings › Web search*): **DuckDuckGo** by default (free, no setup; it has no
  official search API, so valcoach reads its plain results page, and it blocks a server for a while after many
  searches), your own **SearXNG** server (free; it must allow JSON, see the README) or **Claude's web search**
  (Anthropic key, US$ 10 per 1,000 searches, in the Claude budget). A **backup search** takes over when the main
  one fails or finds nothing, e.g. DuckDuckGo with SearXNG as backup. Set it to *Off* to turn web search off. For each question the model decides whether to look something up (patch changes, abilities, pros,
  KovaaK's playlists; at most three searches), reads the best pages and answers with the pages it used as links.
  Also in *Ask the coach about this round* in reports. Pages are only read from public addresses (never the server
  itself, your LAN or cloud metadata, also after redirects), at most 600 KB, text only. A *Test* button checks it.
- **KovaaK's playlists from the community** on the Aim page: 39 public playlists by share code (the Valorant /
  Counter-Strike routines, ones for a single problem such as micro-flicks, peeking or reactivity, and the Voltaic
  fundamentals by level), from the community list at github.com/officialpure/Resources. The four that fit what your
  matches show, at about your level (from your imported scores), are on top; *Add to routines* puts one in your or
  your team's routines. Paste the code in KovaaK's under *Sandbox › Online Playlists › Enter Share Code* and it
  downloads every scenario. With web search, *Search the web* finds more share codes online.
- **Page width** under Account › Look & feel: *Like the style* (as before: only Data terminal uses the whole width),
  *Centred* or *Full width*, for every style.
- **Backups to a read-only folder are explained**: instead of *[Errno 30] Read-only file system* the error says that
  the systemd service may only write to its data folder and which `ReadWritePaths=` line to add. Saving a backup folder
  in Settings now checks that valcoach can actually write there.
- **Security (found by GitHub's CodeQL scan):**
  - Redirects after logging in, switching the language and the Aim page's buttons only go to pages of valcoach.
    Before, a crafted link such as `/login?next=/\evil.example` could send someone to another site after logging in
    (browsers read `/\` and `/<tab>/` like `//`).
  - Web search errors shown in the browser (Settings › Test, Ask the coach, the Aim page) are fixed texts now;
    the details from the search server or the exception only go to the server log.
  - The backup folder must be a full path without `..` inside `/mnt`, `/media`, `/srv`, `/home`, `/backup(s)`,
    `/var/backups` or the data folder. Other places: list them in the environment variable `VALCOACH_BACKUP_ROOTS`
    (separated by `:`), e.g. in the systemd service.
- German for everything new.

## 4.1.2
- **Fix: valcoach didn't start on Python 3.11.** One line in the agent details (utility note) used nested f-string
  quotes, which only Python 3.12+ can read, although 3.11 is supported. 3.12 and 3.13 (Docker) weren't affected.
- **The tests now run on Python 3.11 and 3.12**, and a linter (ruff, settings in `pyproject.toml`) checks every pull
  request, so syntax a supported Python can't read, undefined names and leftover imports are caught before merging.
  Run it locally with `ruff check valcoach tests` (it comes with `pip install -e ".[dev]"`).
- **Ollama retries wait** (2 s, then 4 s, at most 8 s) when the server can't be reached or answers with an error,
  e.g. while it's still loading the model, instead of trying again instantly and failing. A reply that isn't valid JSON
  is still retried right away.
- With Claude and the local model as fallback, Claude now gets the caller's retry setting too.
- An unknown coaching mode (not `both`, `team` or `player`) stops with a clear message instead of a crash halfway.
- Server errors show valcoach's error page (with a hint to check the server log) instead of a bare *Internal Server Error*.
- Dependabot keeps the GitHub Actions in the workflow up to date.
- Tests: the Premier page test no longer expects a fixed map (it failed once the season reached week 3), and the
  *Ask the coach* test waits longer, so it doesn't fail on a busy machine.
- Cleanup: unused imports and variables removed; `.git` is no longer sent to Docker builds.
- README: install and update with git instead of a zip, what the server needs (GPU memory for the model, CPU for the
  video part, disk space for VODs), *Known limits* updated for the fixes from the first real recording.
- `valcoach-fixes.patch` is removed (everything in it has been in the code since 2.17.0) and `CHANGES.md` moved to
  `notes/review-fixes-2.15.md`.

## 4.1.1
- KovaaK's playlists from the coach carry the date (DD-MM-YYYY) in their name and file name, e.g.
  *valcoach warm-up 03-11-2026* in `valcoach_warmup_03-11-2026.json`: older ones can stay in the Playlists folder and
  you can tell them apart. A second download on the same day has the same name and replaces that day's file.
- The training playlist is no longer the warm-up with more runs: it plays **other scenarios** than that day's
  warm-up, at most two runs each (about 10–13 different ones), medium first and then harder ones for what your
  matches need, and ends with something different (a kind you don't train otherwise, often tracking). A scenario
  is only repeated when your scenario list has nothing new left.

## 4.1.0
- **KovaaK's playlists from the coach** (Practice › Aim): a **warm-up** (~10 min) and a **training** playlist (~25 min),
  built from what your matches show and changed every week. *Download for KovaaK's*, save the file in
  `FPSAimTrainer › Saved › SaveGames › Playlists` (it replaces last week's) and open it under *Local Playlists*;
  scenarios you don't have yet download by themselves.
  - A low headshot rate gets micro-adjusting and head-level scenarios, losing first duels gets reaction and peeking
    ones, and so on. Each scenario shows what it trains, its level and your best and last score.
  - The coach's warm-up is a routine like the others: tick it off, make it your or the team's warm-up (match screen,
    Home, practice plan, the push before the match). Anyone with imported scores gets it as the default warm-up.
- **Your KovaaK's scores:** import the `.csv` files from `FPSAimTrainer › stats` (or the folder as a zip; runs already
  imported are skipped). Per scenario: runs, best, last, a small chart and the trend. Once you're steady near your best
  on a scenario, the next playlists use harder ones of the same kind. Days with a KovaaK's run count as warm-up days
  in *Does warming up help?*
- **More scenarios for the coach:** 53 are built in (all from well-known playlists). Add your own: import playlist
  files (every scenario in them joins the list, and the playlist itself becomes a routine with its share code), add
  one by hand with what it trains and its level, or let them come in with your scores. Per user or for the whole team.
- German: messages made of several sentences are translated sentence by sentence.

## 4.0.0
- **Deutsch:** the whole interface in German, picked per user under Account › Look & feel › Language (English stays
  the default). Menus, every page, buttons, messages, confirmations, the minimap replay and notifications on your
  phone. The login page follows the browser's language and has a Deutsch / English switch.
  - **Discord posts** have their own language per team (Team settings › Discord › Language of the posts).
  - The coach's texts (reports, reviews, tips, quiz) stay in each player's coaching language, as before. People's
    own notes, strat names and drafts are never changed.
  - The change notes on *What's new* stay in English.
  - How it works: pages are written in English and translated on the way out from one list
    (`valcoach/i18n/de.json`). Text that scripts add later goes through the same list in the browser. Anything
    missing from the list simply stays English, so a new feature never breaks the German interface.
- **Menu at the top fits any width:** the bar measures itself and shrinks step by step only as far as needed
  (icons, your name and uptime, the picker names, the logo text, spacing, finally group icons only). Long player and team
  names or the longer German labels no longer run into the icons on the right.
- Examples and placeholders are generic now (`Name#TAG`, *teammate1* in the example playbook, all regions in the
  region hint) instead of one player's names.

## 3.8.0
- **Aim** (Practice, per player): aim routines and a warm-up before matches.
  - **Routines:** five built-in ones for the Range and Deathmatch (warm-up, headshot-only, peeking, micro-adjusting,
    spray), plus your own and your team's: an **Aimlabs share link** (opens Aimlabs and offers the playlist), a
    **KovaaK's share code** (with a copy button), any other link, or steps. Each says what it trains.
  - **For you:** the routines that fit what your matches show: a low headshot rate → crosshair placement and
    micro-adjusting, losing first duels → peeking and flicks. Match data shows *that* you lose duels, not *why*,
    so the page says so and you can pick anything else.
  - **Your warm-up:** the one you pick, else the team's warm-up (the owner sets it), else the
    shortest routine marked *Warm-up* (yours and the team's before the built-in ones).
    It shows on the match screen and the Home banner on match days, is the warm-up item in the practice plan, and
    comes as a notification 30 minutes before the match (Account › Notifications › Warm-up).
  - **Done today**, with an optional score you type in (valcoach can't read Aimlabs or KovaaK's). Your scores per
    routine are listed, and after a few weeks the page compares your headshot rate on warm-up days with the other days.
- Inputs without a type no longer look greyed out (review evening note, new aim form).

## 3.7.0
- **Review evening** (Practice): go through one match round by round together, on a shared screen or each on his own.
  - Pick any match two or more of you played (or *Review it together* on a Premier review). Whoever starts it hosts:
    he moves from round to round, everyone who follows the host jumps along. Arrow keys move, *Key rounds only*
    jumps through the rounds that decided the match.
  - Every round: won or lost and how, both teams' buys, the first kill, the plant, who was alive at the end, deaths
    nobody traded, the kill feed, your five players' numbers and the minimap replay.
  - Everyone marks his own round: **my fault**, **good** or **talk about it** (keys 1, 2, 3), with a short note.
    The strip at the top shows which rounds are marked; everyone's marks show up live.
  - **Summary:** the rounds to talk about with the notes, every player's rounds, and what keeps coming up in the
    rounds you flagged (deaths nobody traded, thrown leads, post-plants...). The host puts that into this week's
    practice plan (it stays in when the plan is made again), the owner can post it to Discord.
- **Round types for scouted opponents** (Opponents › a team): their pistol, eco, force and full-buy win rates, what
  they buy after a lost pistol, the round after a won pistol, post-plants and retakes, with lines like *after a lost
  pistol they force-buy 70% of the time*. The important ones also show up in *How to play them* and on the match
  screen. Teams scouted before 3.7 get it with *Scout again* (the matches are cached, so it's quick).
- **Server page:** how much of the model is in GPU memory (*9.1 of 12 GB on the GPU*), a warning when part of it
  runs on the CPU, and the context length.
- Fixes: sub-points on *What's new* are a list again instead of one long line; a damaged draft no longer breaks the
  Drafts page; error pages no longer show a menu entry as the current page.

## 3.6.0
- **Agents & roles › an agent in detail** (*Details* next to every agent):
  - **Progress over time:** your combat score game by game (5-game average) with each win and loss, and your first
    games on the agent against your latest (ACS, win rate, K/D).
  - **Utility per agent:** how often you use each ability per round (by name, e.g. Updraft, Tailwind), against
    everyone else on that agent in your matches, with a note when you use something much less than others.
  - **You against your lobbies:** combat score, kills, deaths, assists, first duels and headshot rate against every
    other player on the same agent in your matches, with where you stand (*better than 63 %*).
- **Agent × map:** win rate and games for every agent on every map in one grid, good and bad cells coloured.
- **Rounds & economy** (Performance): pistol, eco, force and full-buy win rates (per side), uneven buys (anti-eco,
  force against a full buy, eco against a full buy...), the bonus round after a won pistol, post-plants, retakes,
  and rounds where you bought while the team saved. Plain-language findings when something stands out.
- **Teammates** (Performance): everyone you played with 3+ times: games, win rate, your combat score with them, premade
  or random, on which maps; best and weakest duo; solo against with a party.
- Games now also store ability use, every round's buys, your teammates and everyone's numbers by agent. Games loaded
  before 3.6 get them with the next *Load new games* (rebuilt from the stored matches, nothing is downloaded again;
  the nightly sync does it for team members). The pages say when that's still missing.

## 3.5.0
- **Habit tracker** (Practice › Habits, per player): six habits that cost rounds, measured game by game: dying far
  from the team, deaths nobody trades, losing the first duel, rounds without impact, a low headshot rate, and dying
  at the same spot (named, e.g. *Dying at B Main on attack*).
  - Your last 10 games with round data against the 20 before: **Gone**, **Getting better**, **Still there**,
    **Getting worse** or **Fine**, with both numbers, the line where it starts to cost rounds, and a small chart of
    the last 20 games.
  - **What the coach said:** problems named in your reports and Premier reviews are matched to a habit by their
    words, with the numbers before and after that report: *better since*, *no change since*, *worse since*. Tips that
    don't match a number are listed below, the most repeated first.
  - A drill for every habit that's still there, and *Make it my focus* for this week.
- **Practice plan** (Practice › Practice plan, per team): this week's sessions, made instantly every Monday (no
  model needed) from the team's habits, this week's map and its strats and lineups, and the newest Premier review.
  - Every session: warm-up, a team drill for the habit most players still have (with who it's for), the week's map
    (attack strats one day, defense the next, then lineups), a review together, and play time. The practice before a
    match day becomes match prep with the brief and the match screen.
  - Anyone in the team ticks items off and adds their own; the owner sets days, start time and length, makes it again
    and posts it to Discord. Below: each starter's two open habits with a solo drill.
  - Reminder 60 minutes before each session: on Discord (switch it on) and as a push notification (*Practice*,
    can be switched off under Account).
- **Menu at the top:** your name and the uptime next to your avatar, like in the left menu (hidden on narrow
  screens).
- Ctrl+K finds Habits, Match screen and Practice plan.

## 3.4.0
- **Match screen** (Match day › Match screen): everything for the match you're playing on one page, made for a
  second monitor or a phone next to you. The map, an **Attack / Defense** switch (keys `A` / `D`), the comp with
  everyone's agent and weekly focus, who's playing, the game plans for that side with every player's step, your
  strats (*Play* opens them right there), lineups for that side (your agent first) and, once you know who you got,
  the opponent's scouting. Your own lines are highlighted. `F` for full screen.
- **"Live" from your match times:** valcoach doesn't read the game, but it knows your match days and match time
  (*Brief before each match*). From 90 minutes before until 3 hours after, Home shows *Open match screen* first and
  the menu marks *Match screen* as **Live**.
- **Install valcoach as an app** (Account › Install as an app): on Android, iPhone, Windows and Mac. Own icon,
  own window, starts fast (the look is kept on the device), and an *offline* page when the server isn't reachable.
  No app store. Pages and your data are never stored on the device.
- **Push notifications** (Account, per device): *Report ready* when a coaching report you started is done (or
  failed), and *Match day* 90 minutes before your match with a link to the match screen. Switch each kind on or off;
  *Send a test*. iPhone and iPad need the installed app (iOS 16.4+). The server makes its own keys; nothing goes
  through a third-party service except the browser's own push service. Needs HTTPS (you have it through NPM).
- **Share a report:** *Make a share link* on a finished report's page: a read-only link a teammate can open
  without an account (the recording plays too). *Stop sharing* turns the link off at once.
- New dependency: `pywebpush` (installed by `pip install -e .`).

## 3.3.0
- **Unrated counts too:** *Import match history* / *Load new games* now also load your Unrated games (the last
  ~60 with round data and up to 300 older ones, like Competitive and Premier). The first import after the update
  takes a bit longer and uses more HenrikDev requests; later ones only fetch what's new.
- Two more queue tabs on Stats & maps, Agents & roles, Rank & progress and Pros & videos: **Unrated** and
  **Everything** (ranked + Unrated). *All ranked* stays Competitive + Premier, so your ranked numbers don't change.
  Team comps can use *Everything* too (Team settings › Use games from).
- Rank over time still only uses Competitive (Unrated has no RR).

## 3.2.0
- **Agents & roles** (Performance › Agents & roles, per player):
  - **What you pick:** the agent class you play most (Duelist, Initiator, Controller, Sentinel) with games and win
    rate per class, your most played agent, the class where your numbers are best compared with your own average,
    and the role a team owner set for you.
  - **What your habits fit:** the team role your games point to (Entry, Second entry, Lurker, Anchor, Support) with
    the numbers behind it, all role scores 0–100, and IGL / Operator on top when they score high. Says *clear fit*,
    *leaning* or *no clear role yet*.
  - **Suggestion:** whether the two match, if not which class suits your habits better, a note when your team gave
    you a different role, and three agents to try (the most picked at your level first).
  - **All your agents:** every agent you played with games, win rate, ACS, K/D, ADR, KAST, first duels and how many
    of them you won, best map; sort by any column, open the numbers per map. Agents you haven't played yet below.
  - All ranked / Competitive / Premier like the other pages.
- *Stats & agents* is now called **Stats & maps** (its focus is the maps; the agents have their own page).
- Ctrl+K finds the new page and the newer team pages (This week, Availability, Match-day brief, Opponents).

## 3.1.0
- **Menu at the top or on the left** (Account › Look & feel › Menu). *At the top* puts the same menu in a bar across
  the page: the team and player pickers, then *Home* and the five groups as dropdowns (they close when you click
  elsewhere or press Escape), and What's new, Server, Users, Settings, your account, light/dark and log out as
  icons on the right. The group you're in is underlined. On narrower screens the bar drops the icons and labels it
  can do without; on a phone the menu is always behind ☰. Works with every style.

## 3.0.2
- **Fix:** on the match-day brief the comp's agent pictures overlapped the player names. The comp now shows as five
  tiles (agent picture, agent, player, backup pick) like on *This week*; long names are shortened with "…" and shown
  in full on hover.

## 3.0.1
- **Fix:** the team and player pickers at the top of the menu were see-through in the *Neon glass* and *Tactical
  HUD* styles, so the open list overlapped the menu behind it. Lists, the search box, messages and the phone menu
  now always have a solid background.
- The pickers close when you click anywhere else or press Escape.

## 3.0.0
**New design.** Every page was rebuilt on one design system; all features, data and links stay the same.
- **One menu for everything**, on the left (a ☰ button on phones). At the top you pick the *team* and the *player*
  it works on (opening a team or player page picks it for you). Below, five groups that open and close:
  *Match day* (This week, Availability, Match-day brief, Opponents), *Strategy* (Comps, Drafts, Game plans,
  Strat book, Lineups), *Performance* (Matches & reports, Stats & agents, Rank & progress), *Practice* (Training,
  Weekly focus, Quiz, Pros & videos) and *Roster & setup* (Roles, Team notes, Player & playbook, Team settings).
  The menu remembers which groups you opened; *This week* shows the week's map, *Quiz* how many questions wait.
- **Every page starts the same way:** where you are, a title that matches the menu, one line of context, and the
  page's buttons on the right. Map and queue switches are one kind of tab everywhere.
- **Home:** the week's map large at the top (with the minimap behind it), who can play on the next match day as
  one chip per player and your Yes / Maybe / No right there.
- **This week (Premier):** the comp as five agent tiles, the season as week tiles with the current week marked,
  match days as toggle buttons, results as *Won* / *Lost*.
- **Reports** use the same colours and type, with the score green or red.
- **Light and dark** with the moon button at the bottom of the menu (standard style).
- **Styles rebuilt** for the new layout: Esports broadcast, Clean minimal, Neon glass, Tactical HUD, Data
  terminal, Editorial magazine, Coach's playbook, Retro arcade, and new *Original red* (the colours before 3.0).
  Account › Look & feel shows a real preview of each.
- **Fonts ship with valcoach** (Archivo and the styles' fonts, all OFL licensed, in `static/fonts`): nothing is
  loaded from Google any more.
- Colours mean one thing each: amber = something you can do, teal = good or won, coral = bad or lost.
  Labels are no longer in capitals.

## 2.25.0
- **Home page "Today":** everything for today in one place, instead of clicking through five pages.
  - Per team: this week's map with the match-day brief, the next match day with who's playing (and who could sub),
    your own ✓ / ? / ✗ for it right there, and your focus.
  - For you: warm-up done or not and your streak, your rank and the change in 14 days, a quiz waiting, your last
    report.
  - Jobs running or failed in the last day, and what teammates changed since your last visit (strats, drafts,
    notes, Premier reviews). New accounts get three first steps instead.
- **Simpler navigation:** *Home*, *Teams*, your own player (the one named like your in-game name under Account) and
  everyone else under *Players ▾*, instead of every player in the top bar. Player links open Stats & agents.
- **Team tabs grouped:** *Match prep* (Premier first, then Comps, Drafts, Game plans, Strat book), *Players* (Weekly
  focus, Roles, Notes) and *⚙ Settings* (members, maps & Discord).
- **Faster pages:** players' game files are read once per change instead of on every page, and a team's comps,
  roles and tips are kept until the team or someone's games change.
- **Backups** (Settings › Backups, on by default): every night from 04:00 the database, players, teams, notes,
  strats and reports go into one .tar.gz, the newest 14 are kept. Set the folder to your NAS. *Back up now*, and
  the last backup shows in Settings and on the server overview.
- **Reports:** filter the rounds: ★ lessons, leads thrown, your deaths, lost rounds.
- **Discord:** optional channels for Premier reviews and for clips (empty = #match-prep as before).
- **Settings:** a section menu at the top (match data, local model, Claude, video, pros, server, backups).
- Smaller: the empty Progress and Training pages have an *Import history* button; schedule times say which time
  zone the server uses.

## 2.24.0
- **Ask the coach about a round:** under every round of a report opened in valcoach, ask a question ("Should I
  have saved?", "What if I'd waited for the flash?"). The model gets that round's facts and its own feedback,
  answers in a few sentences, and the questions and answers stay with the report. Pick the model next to *Ask*.
  Works on older reports too.
- **Clips:** next to the VOD jump buttons in a report (round start, first kill, your death…), *⬇ clip* cuts 15
  seconds from there as an MP4 (720p, with sound) and *→ Discord* posts it to your team's channel. Clips are
  kept, so the second time is instant. Needs ffmpeg on the server: `sudo apt install ffmpeg`.
- **On the map** (Stats & agents › a map): where you die (red) and get kills (green), drawn on the minimap at the
  callout, for attack and defense; bigger = more often.
- **AFK in reports:** rounds where a teammate was AFK or never left spawn (Riot's own flags) get a chip.
- **Strat history:** *History* in the strat editor lists earlier versions of the board (one per 10 minutes of
  editing, and one whenever someone else edits) with who saved it; *Restore* brings one back, and the board as it
  was stays in the history.
- **Test buttons** in Settings for the HenrikDev key, the Anthropic key (also says if an offered model isn't
  available to the key) and the Ollama model.
- **Tests on GitHub:** every pull request and every push to main runs the test suite (GitHub Actions). The PR
  shows a green check or a red cross before you merge.

## 2.23.1
- **Last active** on Users: when each user was last on the site (any page, updated at most once a minute), with
  "● online now" for the last 5 minutes. *Last login* only changes when someone types their password, and logins
  last a long time, so it said little. Also on each user's page, and the server overview counts who's online.

## 2.23.0
- **Claude as a model, picked per run.** Next to every button that runs the model (Start coaching, tips, what to
  watch, game plans, weekly focus, Premier reviews, the quiz) there's now a model picker: your local default, the
  other models installed in Ollama, and with an Anthropic API key Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 (☁).
  - Your last pick is remembered as the default for the next run. *All maps* and *Run again* use the same model.
  - *Settings › Claude*: API key (also `ANTHROPIC_API_KEY`), which Claude models are offered, a **monthly budget**
    (Claude stops when it's spent), and **fallback**: if Claude can't be used (no key, no credit, budget used up,
    API down), the local model finishes the job and the report says so.
  - *Model for automatic jobs*: what the nightly Premier reviews and the weekly focus use.
  - Only admins and users with **Can use Claude** (Users › user) see the Claude models; the server checks it too.
  - What it costs: every request is priced from its tokens (Anthropic's October 2026 prices). The report header
    shows the cost of that run; the server overview shows today, this month per model, the budget and the last
    30 days.
- Any other installed Ollama model can be picked per run too, to compare models on the same match.

## 2.22.0
- **Quiz → practice:**
  - After each answer: *🎯 Make this my focus* sets the best call as your own focus for this week. It shows on
    Training, on the team's Weekly focus page next to the coach's pick, and in the match-day brief.
  - Every answer is saved per category (alone at the end, first death far from the team, a lead that slipped). The
    quiz page shows how often you pick the best call in each one. A category under 60% (with 3+ answers) shows up
    on Training under *What to work on*, with a decision drill.
  - Rate each question as *good*, *unrealistic* or *too obvious*. The next quiz gets the good ones as examples and
    the others as what to avoid.
- **👍 / 👎 on reports:** every line of the coach's round feedback (key moment, mistakes, better option) can be
  rated. Liked lines become examples for your next coaching runs, next to your own notes; disliked ones are what
  the coach should avoid. On your own lines, *🎯* makes one your focus for the week. Works on reports made from
  2.22 on, opened from valcoach.
- **Faster notes:** one-click tags under every round ("died alone", "late rotate", "util too early"…), and what the
  coach said about the round last time is shown greyed out, so you can correct it in your own words. It's never
  filled in for you: the notes only help because they're yours.
- **Strat playback for the IGL:** each step can have a call ("1:20 Omen smokes B Main, Jett dash in behind"), shown
  big on the map while it plays. *Step by step* makes the playback wait for a click (or Space / →) before each
  step, for walking the team through it in voice.
- **Availability:**
  - Notes like "from 21:00" show on the day cards, in the brief and in the Discord brief.
  - *🔔 Remind* posts who hasn't answered for the next match days to Discord.
  - With a player's Discord user ID (Availability › Discord IDs, owner only), the reminder pings them; only those
    IDs can be pinged, never @everyone.
- **Rank over time:** games with a coaching report are ringed and open the report on click.
- Fixed: a Premier roster sync forgot "Use my own list" (the team maps went back to following the stage pool).

## 2.21.0
- **"This week" works again on the Premier tab.** HenrikDev's season data still lists an older season, and that
  replaced the built-in stage, so no week matched today. Now the API's schedule is only used when it covers today;
  otherwise the built-in stage (V26A6) is, with a note saying why. Between two weeks the card names the next map.
  Team owners get a *Raw season data* link under the stage schedule to see what HenrikDev returns.
- **Availability** (Premier › Availability): everyone marks ✓ / ? / ✗ for the match days of the next two weeks (the
  days from *Brief before each match*), with a short note on right-click ("from 21:00"). Each day shows who's
  confirmed, who hasn't answered, and the five planned for that day's map (your *main* draft, else the suggested
  comp). If a planned player can't play, the free players are ranked by games on that agent, then on that role.
  Players change their own row once linked to their player; the team owner can change all rows. The brief, the
  Premier overview and the Discord brief show "who's playing" too.
- **Rank over time** on Progress: your rank and RR after every ranked game as a line with tier bands, the change
  in the last 14 days and your peak. The RR history is loaded on *Import* and kept locally (HenrikDev only keeps a
  window of it); without it, the rank shown in each match is used.
- **Strat playback:** *▶ Play* in the strat editor (or ▶ on a board in the list) animates the steps: agents and
  abilities move to their next spot, new things fade in, removed ones fade out, with the step name on the map.
  0.5×, 1× or 2×; Esc or a click on *Stop* ends it. New steps remember what they were copied from, older boards
  are matched by agent.
- **Quiz** (new player tab): moments from your own last games (left alone in a 1vX, a first death far from your
  team that nobody traded, a lead of two or more that slipped) become questions with 3-4 calls. The model writes
  them from what you could know at that moment; after you answer you see the best call, why, and what really
  happened. Scores are kept.
- **Server overview** (click the uptime clock, or Users › Server overview): HenrikDev requests per minute and per
  day, rate limits hit, whether the model is online and loaded, background jobs running or failed, the scheduler,
  and disk use per folder. Admins can give it to anyone (Users › user › *Can see the server overview*) without
  making them admin. It shows no keys, logs or anyone's games.
- Fixed: the progress text of running scouting, match reviews and schedule jobs on the Premier pages never
  updated (the status check treated them as players).

## 2.20.0
- **Nine styles**, picked per user under *Account › Look & feel*. Each one changes the whole look and layout, not
  just the colours: **Classic** (as before), **Esports broadcast** (VCT overlay: condensed type, angled red bars),
  **Clean minimal** (light, soft cards), **Neon glass** (purple and teal glow, frosted panels), **Tactical HUD**
  (like Valorant's own interface: teal lines, cut corners, a grid), **Data terminal** (menu on the side, dense,
  monospace numbers), **Editorial magazine** ("The Valcoach" masthead, serif headlines on paper), **Coach's
  playbook** (a clipboard with lined paper and sticky notes) and **Retro arcade** (pixel font, CRT scanlines).
- **Animations with a switch each** (Account › Look & feel): numbers count up, clickable cards lift on hover,
  smooth page changes, progress bars with the current step instead of the raw log for running jobs (the log is
  one click away), and toasts for messages like "Saved". With *reduce motion* set on your computer they stay off.
- **Quick search:** Ctrl+K (or /, or the search button in the top bar) jumps to any player and their tabs, any team
  tab, a map's game plans or drafts, a draft or a strat board.
- **Lineups library** (Strat book › Lineups): one entry per lineup with the agent, ability, side, site, a clip link
  (YouTube shows a thumbnail) and a note, per map and filterable. In the strat editor, a selected ability shows its
  lineups for the map. Only https links are accepted.
- **Phones:** every page checked at phone width, nothing scrolls sideways any more (wide tables scroll inside
  their card).

## 2.19.1
- **Premier stage schedule:** which map is played in which week, read from the Premier season data (HenrikDev),
  refreshed once a day and with the nightly sync. If the API doesn't give the maps, the current stage (V26A6: Bind,
  Corrode, Sunset, Haven, Summit, Abyss, Lotus, playoffs 6 December) is built in.
  - The Premier tab shows the stage week by week with dates, this week highlighted, and your results per week.
  - **A Premier team's maps follow the stage's map pool** (in week order), so Corrode and Summit show up everywhere
    (Comps, Drafts, Game plans, Strat book). *Use my own list* on the Premier tab switches back to the maps you set.
  - Game plans, Drafts and Comps open on this week's map.
  - Monday/Tuesday between two weeks already counts as the coming week, so the brief and plans are for the next map.
- **Summit** added to the known maps.

## 2.19.0
- **Progress** (new player tab): the last 10 weeks, week by week, for win rate, ACS, K/D, KAST, first duels won,
  deaths traded, deaths far from the team, rounds survived, headshots, clutches, retakes and ADR. Each one shows
  the trend (last 2 weeks vs the 6 before) in green or red.
  - **Did the weekly focus work?** For every focus you got, the number it was about, before and in the games since,
    with the goal and a verdict (goal reached / better / no change / worse). The *Weekly focus* tab shows the same
    for last week's focus next to every player.
- **Clutches, retakes, post-plants** (on Progress): 1v1 to 1v5 won/played, retakes won when they planted while you
  were alive, and post-plants won when your team planted.
- **Training** (new player tab):
  - **Aim fundamentals:** your headshot share, and your fights by range (under 10 m, 10–25 m, over 25 m): how many
    you take and how many you win. Also first duels and deaths far from the team.
  - **What to work on**, and **your warm-up**: about 20 minutes of drills in Valorant's Range and modes, picked
    for your weak spots. *Done today* keeps a streak (last 14 days shown).
  - **Learn from your teammates:** who in your team is best at what you're weakest at.
  - **Agents to learn: up to 5 instead of 1**, each with a learning path: learn the kit (guide videos), watch a pro
    who plays it, 5 unrated games, lineups for your maps, 10 ranked games, Premier-ready (15 games, 50%+ won). The
    steps tick themselves from your games on that agent. The *Roles* tab lists the 5 too.
- **Timing windows** (Game plans): when your first fight, your plant and the flank kills usually happen on each map,
  and when attackers first make contact on each site on defense, on a 0–100 s timeline, plus when your lurker
  should be in position.
- Game data is read again from the match cache once (new numbers: shots, fight distances, clutches, retakes):
  nothing to download.

## 2.18.0
- **Premier tab** (new team tab), built around how Premier works: the map is fixed for the week, the opponent is
  found only when you queue, and always from your own division.
  - **This week:** the week's map (from the Premier schedule, from your first match this week, or set by hand),
    your comp for it (the draft marked *Our comp*, else the suggested comp), your record on the map, and who in your
    division is strongest there.
  - **Match-day brief:** one page (made for the phone) with the comp, your numbers on the map, the game plans,
    everyone's weekly focus and who you might meet. Posted to #match-prep automatically before your matches: pick
    the match days, the time and how many minutes before. *Post brief to Discord now* works any time.
  - **Division & scouting:** every team in your division is scouted in advance from its recent Premier matches,
    and refreshed every night. When you get matched their page is already there. Teams from outside the list
    (playoffs) can be scouted by Name#TAG.
  - **A team's page:** how to play them (strong and weak maps, who takes their first duels, sites they hit, fast
    or slow executes, lost retakes, pistols), their players and agents, their comps per map.
  - **Map veto for playoffs:** your record against theirs on every map, with which maps to ban first, which to
    pick, and which side to start on.
  - **Automatic match reviews:** every night, new Premier matches get a team review (MVP, the rounds that decided
    it, one thing for each player, who traded whom), posted to #match-prep. The page shows every player's review.
    Only new matches, never old ones; *Review new matches* runs it right away.
- **Phones:** the top navigation turns into a menu button on small screens, and the team tabs scroll sideways.

## 2.17.1
- **VOD uploads go up in 16 MB pieces.** Size limit, report limit and free disk are now checked before the first
  byte is sent, not after the whole file has arrived, and a lost connection only repeats one piece. No request may
  be bigger than 17 MB any more, so nobody can fill the disk without logging in. Temp files stay in `data/tmp`.
  A proxy in front of valcoach must allow bodies of at least 17 MB.
- **API keys stay out of error messages.** A network error could show the YouTube key or a Discord webhook URL on
  pages teammates can open. The YouTube key now goes in a header, and Discord errors no longer contain the URL.
- **A report no longer says "done" when the model failed.** If it fails on every round, the job ends with an error
  and the reason. If it stops answering, the run stops waiting after a few rounds instead of timing out on all of
  them. If only some rounds fail, the report says which ones at the top.
- **A playbook with the wrong structure no longer breaks a run.** `maps` must list each map by name; the profile
  form now says so when you save it.

## 2.17.0
- **Drafts** (new team tab): roster drafts per map, made together.
  - Five player slots (starters or subs). Drag agents from the list onto a player, add a backup pick, drag between
    slots to swap, drag out to remove, or click a slot and then an agent. Works with mouse, pen and touch.
  - Start empty (your starters already in the slots) or from one of the 3 suggested comps for the map.
  - Every slot shows that player's numbers on the agent (games and win rate on this map and overall) and their
    best agents on the map to pick with one click.
  - *Check*: role mix, and warnings for the same agent twice, a player in two slots, no controller / initiator /
    sentinel, 3+ duelists, and players who haven't played their agent yet.
  - Status *Idea / Trying / Our comp*, a role or job per player ("IGL", "lurk B"), notes from your discussions,
    *Duplicate*, *Post to Discord* (#match-prep). Saves by itself; the list shows everyone's drafts per map.
  - Only team members and real agents are stored (same idea as the strat board): nothing another member saves
    can run in your browser.
- **VOD fixes from the first real recording** (in 2.16.0 on GitHub, details in [notes/review-fixes-2.15.md](notes/review-fixes-2.15.md)): big
  uploads no longer fill `/tmp`, ultrawide recordings (black bars) work, "Based on side" minimap orientation is
  calibrated, the minimap summary no longer counts 11 allies, your own icon is followed from your API positions.

## 2.16.0
- **Pro & videos: pick the pro.** Click any of the 3 pro cards to select it. Everything below then follows that pro:
  - the white marks on your playstyle bars,
  - a "Copying <pro>" box with what to take over from them and habits to practise,
  - **What to watch**: searches built around that pro (them on your shared agent and map, how they do the thing
    they're better at than you, their other agent, your weakest map with their VODs), plus your own habit fixes.
  - Each pro gets its own guide. *Write what to watch for <pro>* writes the selected one; *All 3 pros* writes all
    three in one go (one model run each) so switching is instant. Cards show "✓ guide written".
  - Guides written before this version still show for your closest pro.
- **Includes Manuel's review fixes on 2.15.0** (details in [notes/review-fixes-2.15.md](notes/review-fixes-2.15.md)): real utility numbers from the
  live API, the model now sees the field descriptions (also for the new per-pro watch guide), no "check the VOD"
  without a VOD, deathmatch / team deathmatch / gauntlet can't be coached, time-outs are detected, the strat board
  only stores typed fields (stored XSS), forms from other sites are blocked (CSRF), limits per user (reports at
  once, upload size, free disk), a job can't run twice, safer match IDs and inputs. Requires Flask 3.1+.
- The project is a git repo now: updates come as a commit on top of `main` instead of a zip over the folder.
- **Uptime clock** in the top bar: how long valcoach has been running, ticking live. Hover it for the start time
  and how long the server itself has been up.

## 2.15.0
- **Nightly sync.** Every team syncs by itself every night at 02:00 (server time): the Premier roster first (if the
  team is linked to Premier), then everyone's stats, just like pressing the two buttons. On by default; change the
  hour or turn it off under *Members, maps & Discord* → *Automatic sync*. If the server was off at that hour it
  catches up within 3 hours. The buttons still work any time, and the team header shows "syncs nightly 02:00".
- **Roles table sorts.** Click a column (IGL, Entry, …, or Player): ascending, click again for descending, a third
  time for the normal order. Your ticked roles move with the rows.
- **Game plans:** the 3 comps are tidy now: each comp is one row of 5 (agent + player), with the role mix written
  out underneath ("1 duelist, 2 initiators, …") instead of wrapping onto a second line.

## 2.14.0
- **Strat book: abilities look and size like in the game.**
  - Smokes are drawn at their real radius as clouds in the agent's colour (Omen purple, Brimstone tan, Viper green,
    Astra violet, Clove pink, Harbor blue, Jett pale blue, Cypher white), so you can tell whose smoke is whose. The
    outline still shows us / enemy.
  - Line and area abilities are full shapes you aim from where they're cast: **Fault Line** (7.5 m wide, 8–56 m),
    Rolling Thunder, Armageddon, Hunter's Fury, Nightfall, Paranoia, Cascade, Contingency, Kill Contract... Drag the
    yellow handle to aim, and stretch where the ability can.
  - Walls have their length: Toxic Screen (up to 60 m), Blaze, High Tide, Barrier Orb, Trapwire, Cosmic Divide;
    Fast Lane is two walls.
  - Mollies, slows, stuns and reveals are circles at their size (Snake Bite, Nanoswarm, Lockdown...).
  - Sizes from the Valorant wiki where it lists them; the rest are marked *estimated* on the board. Every radius
    and length can be changed per item (↺ puts it back).
- Click an ability (no drag) to drop it at that agent on the board: lines start at the agent and point into the map.
- Select an agent on the board and its abilities show up under *Selected*.
- The generic Smoke and Molly shapes are gone from the palette (use the agent's ability instead); boards that
  already have them still show them.

## 2.13.0
- **Strat book** (new team tab): boards on the real minimap, saved per team and map, editable by everyone in the team.
  - Drag any agent and every ability of every agent (icons from valorant-api.com) onto the map, plus smokes,
    mollies, stun/slow/flash zones, markers and numbers. Draw arrows (dashed for rotates/lurks), paths, walls, text.
  - Us / enemy colours, a player name under each agent, ability areas with a real radius in meters.
  - Steps (e.g. Setup → Fake A → Lurk timing): a new step starts as a copy, the step before shows faded.
  - Undo/redo, copy, delete, zoom, callouts on/off, keyboard shortcuts; saves by itself.
  - Download a step as a picture, or post it with the notes to #match-prep.
- **Draw it** on every game plan opens it on the strat board, with the plan's steps as notes.

## 2.12.0
- **Shared teams:** add teammates' accounts under *Members, maps & Discord*. They see the team (comps,
  game plans, weekly focus, roles, notes) and their teammates' stats, read-only; only the owner changes settings.
  Each picks *Which one is you?* on the team page; an in-game name that matches a player links them automatically.
- **In-game names:** accounts have a display name (e.g. `adv1ce#LFT`), set under Account or when signing up.
- **Notes tab:** notes about the team or a player, per map if you like; everyone in the team sees them.
  Next to them, tips from your matches together (who dies outnumbered or alone where, which duos trade each other).
- **Game plans tab:** per map, the model writes 3 plays (2 attack, 1 defense) with a step for every player by
  name, agent and role, timings, if/then adjustments and the numbers behind it (sites you hit, first-fight timing,
  where you get killed from behind, mid control, what opponents plant). Your notes and roles are used.
- **Weekly focus tab:** one focus per player for the week, from their last 2 weeks vs. before, their team role,
  the data tips and notes about them, with a number to watch. Shown on everyone's dashboard.
- **Discord:** webhooks for #match-prep (top 3 comps per map + game plans) and #weekly-focus; test message;
  automatic weekly focus post on a day and hour you choose. Posts never ping anyone.
- Comps tab: 2nd and 3rd comp options per map.

## 2.11.4
- **What's new page:** click the version next to the logo to see this changelog in the app. After an
  update, everyone sees a one-time note with a link (and a red dot on the version until they've looked).

## 2.11.3
- Fix: Premier import with no member list and only one Premier match so far (start of a season).
  The roster now comes from the team's Premier roster inside the match data, or else from the side
  of the match your own player was on; only then from players who appear in 2+ matches.

## 2.11.2
- Fix: Premier import failed with "returned the team without members" when HenrikDev sends the roster
  with only player ids (name/tag empty). Names now come from the team's Premier matches, then from
  HenrikDev's account-by-id lookup; with no member list at all, the regulars of the team's matches are used.
  The import log says how many members came back and how many had names.

## 2.11.1
- Version number shown in the web app (next to the logo and in Settings), in every report,
  in `valcoach --version`, in the README and in this changelog. Zips are named with the version.

## 2.11.0
- **Premier import:** create a team from your Premier `Name#TAG` + region. Loads the roster, adds the
  players (existing ones reused), picks starters from the last 10 Premier matches, imports everyone.
  *Sync Premier roster* keeps your starter/sub choices and roles. Division, points and record on the team page.
- **Roles tab:** 0–100 fit per player for IGL (a guess), Entry, Second entry, Lurker, Anchor, Support,
  Operator, Flex; assign roles yourself; suggested lineup keeps them; checks when an assigned role doesn't
  show in the data; an agent to learn per player.
- **Whole-team match review:** every teammate gets went well / to fix / how the team can help them;
  *Together* tab with trades, untraded, alone and outnumbered deaths. CLI: `coach --team`.
- Game rows store more per-game numbers (rebuilt from cached matches on the next *Update*).

## 2.10.0
- **Pro & videos tab:** your playstyle as four percentiles vs. your lobbies, the 3 closest pros
  (editable list in Settings), up to 6 targeted YouTube searches, and model-written "watch for" notes.
  Optional YouTube Data API key shows the videos inline.

## 2.9.1
- Teams first in the top bar and on the dashboard; team page split into Comps (all maps at a glance)
  and Members & maps; a role mix set in the map meta is followed whenever possible.

## 2.9.0
- **Stats & agents:** history import (recent full matches + archive), per map / agent numbers, opening
  duels and death spots per side, findings, model-written tips per map, solo-queue pick helper.
- **Teams:** comps per map from everyone's stats, substitutes ("if someone is missing"), map meta.

## 2.8.0
- With a VOD, teammates' paths are measured from your minimap; spotted enemies drawn on the replay.
- Estimated movement between kills at running speed (hold, then move just in time).

## 2.7.0
- Report: round list on the left, sticky replay / video panel on the right; smaller map;
  plain mouse wheel scrolls (Ctrl + wheel zooms); generic "Round N review" summaries hidden.

## 2.6.1 and earlier
- Headless OpenCV (servers without libGL); playable continuous round replay with agent portraits;
  older matches via HenrikDev's archive; accounts, workspaces, systemd/Docker; VOD sync + minimap tracking.
