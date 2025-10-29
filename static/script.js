// script.js

document.getElementById('calculate-button').addEventListener('click', async () => {
    const target_n_char = parseInt(document.getElementById('target-char').value);
    const target_m_lightcone = parseInt(document.getElementById('target-lightcone').value);
    const initial_gems = parseInt(document.getElementById('current-gems').value);
    const initial_tickets = parseInt(document.getElementById('current-tickets').value);
    const initial_pity_5star = parseInt(document.getElementById('pulls-since-last-5star').value);
    const initial_is_guaranteed_5star_pickup = document.getElementById('is-guaranteed').checked;
    const num_simulations = parseInt(document.getElementById('num-simulations').value);

    const response = await fetch('http://127.0.0.1:5000/simulate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            target_n_char,
            target_m_lightcone,
            initial_gems,
            initial_tickets,
            initial_pity_5star,
            initial_is_guaranteed_5star_pickup,
            num_simulations
        }),
    });

    const result = await response.json();

    const expectedProbabilityDiv = document.getElementById('expected-probability');
    const probabilityDistributionDiv = document.getElementById('probability-distribution');

    if (result.error) {
        expectedProbabilityDiv.innerText = `エラー: ${result.error}`;
        probabilityDistributionDiv.innerText = '';
    } else {
        expectedProbabilityDiv.innerText = `現在のリソースで目標を達成できる確率: ${result.success_probability.toFixed(2)}%`;
        if (result.avg_starlight_tickets_in_successful_sims > 0) {
            expectedProbabilityDiv.innerText += ` (星芒によりチケット平均${result.avg_starlight_tickets_in_successful_sims.toFixed(1)}枚相当を追加で獲得)`;
        }
        
        let distributionText = '\n目標達成までのガチャ回数分布と消費星玉:\n';
        if (Object.keys(result.pulls_distribution).length > 0) {
            for (const key in result.pulls_distribution) {
                const pulls = result.pulls_distribution[key].pulls;
                const gemsConsumed = result.pulls_distribution[key].gems_consumed;
                const starlightTickets = result.pulls_distribution[key].starlight_tickets_earned;
                distributionText += `  ${key}の確率で達成: ${pulls.toFixed(0)}回 (星玉${gemsConsumed.toFixed(0)}個を消費, 星芒によりチケット${starlightTickets.toFixed(0)}枚相当獲得)\n`;
            }
        } else {
            distributionText += '  (目標達成できたシミュレーションがありませんでした。)';
        }
        probabilityDistributionDiv.innerText = distributionText;
    }
});