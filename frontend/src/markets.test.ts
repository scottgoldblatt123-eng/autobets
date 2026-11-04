import { describe, expect, it } from 'vitest'
import { groupMarkets } from './markets'

const m = (name: string, market_type = '') => ({ market_id: name, name, market_type, event: '', competition: '', start: null, runners: {} })
const groups = (ms: ReturnType<typeof m>[], ev = '') => Object.fromEntries(groupMarkets(ms, ev).map(([g, l]) => [g, l.map(x => x.name)]))

describe('groupMarkets', () => {
  it('keeps match goals, team goals, corners and cards apart, with lines in order', () => {
    const g = groups([m('Over/Under 2.5 Goals', 'OVER_UNDER_25'), m('AEK Athens Over/Under 2.5 Goals'), m('Real Madrid Over/Under 0.5 Goals'), m('Over/Under 0.5 Goals', 'OVER_UNDER_05'),
      m('Corners Over/Under 8.5'), m('Cards Over/Under 2.5'), m('Match Odds', 'MATCH_ODDS'), m('Correct Score', 'CORRECT_SCORE')], 'AEK Athens v Real Madrid')
    expect(g['Match goals']).toEqual(['Over/Under 0.5 Goals', 'Over/Under 2.5 Goals'])
    expect(g['Team goals']).toEqual(['AEK Athens Over/Under 2.5 Goals', 'Real Madrid Over/Under 0.5 Goals'])
    expect(g['Corners']).toEqual(['Corners Over/Under 8.5']); expect(g['Cards']).toEqual(['Cards Over/Under 2.5'])
    expect(g['Result']).toEqual(['Match Odds']); expect(g['Score']).toEqual(['Correct Score'])
  })
  it('groups tennis sets and games', () => {
    const g = groups([m('Match Odds', 'MATCH_ODDS'), m('Set Betting', 'SET_BETTING'), m('Set 1 Winner', 'SET_WINNER'), m('Total Games', 'TOTAL_GAMES'), m('Set 1 Game 3 Winner'), m('Tie Break in Match', ''), m('Player A Game Handicap')], 'A. Player v B. Player')
    expect(g['Result']).toEqual(['Match Odds'])
    expect(g['Sets']).toEqual(['Set 1 Winner', 'Set Betting'])
    expect(g['Games']).toEqual(expect.arrayContaining(['Total Games', 'Tie Break in Match', 'Set 1 Game 3 Winner', 'Player A Game Handicap']))
  })
  it('puts anything unrecognised under Other rather than losing it', () => {
    expect(groups([m('Mystery Market', 'WEIRD_TYPE')])['Other']).toEqual(['Mystery Market'])
  })
})
