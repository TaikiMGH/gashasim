from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import random
import numpy as np

app = Flask(__name__)
CORS(app) # すべてのオリジンからのアクセスを許可

# ガチャの基本設定 (仕様書より)
# 限定キャラクター跳躍
CHAR_GACHA_RATES = {
    "5_star_base_rate": 0.006,  # 0.6%
    "4_star_pickup_char": 0.0255, # 5.1%の半分
    "4_star_pickup_lightcone": 0.0255, # 5.1%の半分
    "3_star_lightcone": 0.943
}
# 限定光円錐跳躍
LIGHTCONE_GACHA_RATES = {
    "5_star_base_rate": 0.008, # 0.8%
    "4_star_pickup_char": 0.033,  # 6.6%の半分
    "4_star_pickup_lightcone": 0.033, # 6.6%の半分
    "3_star_lightcone": 0.926
}

# 天井設定
PITY_5STAR_CHAR = 90
PITY_5STAR_LIGHTCONE = 80
PITY_4STAR = 10

# ソフト天井開始回数と確率上昇率
SOFT_PITY_START_CHAR = 73 # 74連目から上昇なので、73回目までは基本確率 (0-indexed)
SOFT_PITY_INCREMENT_CHAR = 0.06 # 1連毎に6%ずつ上昇

SOFT_PITY_START_LIGHTCONE = 63 # 64連目から上昇なので、63回目までは基本確率 (0-indexed)
SOFT_PITY_INCREMENT_LIGHTCONE = 0.06 # 1連毎に6%ずつ上昇

# 星芒獲得数
STARLIGHT_FRAGMENTS = {
    "5_star_pickup_char_2_7": 40,
    "5_star_other_char_1_7": 40,
    "5_star_char_8_plus": 100,
    "4_star_char": 20,
    "5_star_lightcone": 40,
    "4_star_lightcone": 8
}

def simulate_single_pull(gacha_type, current_pity_5star, current_pity_4star, is_guaranteed_5star_pickup):
    """
    1回のガチャ試行の結果をシミュレートする。
    :param gacha_type: "character" or "lightcone"
    :param current_pity_5star: 現在の☆5天井までの回数 (0から始まる)
    :param current_pity_4star: 現在の☆4天井までの回数 (0から始まる)
    :param is_guaranteed_5star_pickup: 次の☆5がピックアップ確定かどうか (True/False)
    :return: (排出されたアイテムの種類, 新しいcurrent_pity_5star, 新しいcurrent_pity_4star, 新しいis_guaranteed_5star_pickup)
    """
    rates = CHAR_GACHA_RATES if gacha_type == "character" else LIGHTCONE_GACHA_RATES
    
    # ☆5天井の閾値
    if gacha_type == "character":
        pity_5star_threshold = PITY_5STAR_CHAR
        soft_pity_start = SOFT_PITY_START_CHAR
        soft_pity_increment = SOFT_PITY_INCREMENT_CHAR
    else: # lightcone
        pity_5star_threshold = PITY_5STAR_LIGHTCONE
        soft_pity_start = SOFT_PITY_START_LIGHTCONE
        soft_pity_increment = SOFT_PITY_INCREMENT_LIGHTCONE

    # 5星確定天井
    if current_pity_5star == pity_5star_threshold - 1:
        # 5星確定
        if gacha_type == "character":
            if is_guaranteed_5star_pickup or random.random() < 0.5: # 50%でピックアップ
                result_item = "5_star_pickup_char"
                is_guaranteed_5star_pickup = False
            else:
                result_item = "5_star_other_char" # ピックアップ外
                is_guaranteed_5star_pickup = True
        else: # lightcone
            if is_guaranteed_5star_pickup or random.random() < 0.75: # 75%でピックアップ
                result_item = "5_star_pickup_lightcone"
                is_guaranteed_5star_pickup = False
            else:
                result_item = "5_star_other_lightcone" # ピックアップ外
                is_guaranteed_5star_pickup = True
        
        return result_item, 0, current_pity_4star + 1, is_guaranteed_5star_pickup # 5星天井リセット

    # ☆5の現在の排出確率を計算 (ソフト天井考慮)
    current_5star_rate = rates["5_star_base_rate"]
    if current_pity_5star >= soft_pity_start:
        current_5star_rate = rates["5_star_base_rate"] + (current_pity_5star - soft_pity_start + 1) * soft_pity_increment
        current_5star_rate = min(current_5star_rate, 1.0) # 100%を超えないようにキャップ

    # 通常の抽選
    rand_val = random.random()
    cumulative_rate = 0

    # 5星抽選
    if rand_val < current_5star_rate:
        # 5星が出た場合
        if gacha_type == "character":
            if is_guaranteed_5star_pickup or random.random() < 0.5:
                result_item = "5_star_pickup_char"
                is_guaranteed_5star_pickup = False
            else:
                result_item = "5_star_other_char"
                is_guaranteed_5star_pickup = True
        else: # lightcone
            if is_guaranteed_5star_pickup or random.random() < 0.75:
                result_item = "5_star_pickup_lightcone"
                is_guaranteed_5star_pickup = False
            else:
                result_item = "5_star_other_lightcone"
                is_guaranteed_5star_pickup = True
        return result_item, 0, current_pity_4star + 1, is_guaranteed_5star_pickup # 5星天井リセット

    cumulative_rate += current_5star_rate

    # 4星抽選
    rate_4star_char = rates["4_star_pickup_char"]
    rate_4star_lightcone = rates["4_star_pickup_lightcone"]

    # 4星天井 (10連で4星以上確定)
    if current_pity_4star == PITY_4STAR - 1:
        remaining_rate = 1.0 - cumulative_rate # 5星が出ていないので、残りの確率
        
        total_4star_base_rate = rate_4star_char + rate_4star_lightcone
        
        if total_4star_base_rate > 0: # 0除算防止
            rate_4star_char_adjusted = remaining_rate * (rate_4star_char / total_4star_base_rate)
            rate_4star_lightcone_adjusted = remaining_rate * (rate_4star_lightcone / total_4star_base_rate)
        else: 
            rate_4star_char_adjusted = remaining_rate / 2
            rate_4star_lightcone_adjusted = remaining_rate / 2
            
        if rand_val < cumulative_rate + rate_4star_char_adjusted:
            result_item = "4_star_pickup_char"
            return result_item, current_pity_5star + 1, 0, is_guaranteed_5star_pickup # 4星天井リセット
        else:
            result_item = "4_star_pickup_lightcone"
            return result_item, current_pity_5star + 1, 0, is_guaranteed_5star_pickup # 4星天井リセット

    # 通常の4星抽選
    if rand_val < cumulative_rate + rate_4star_char:
        result_item = "4_star_pickup_char"
        return result_item, current_pity_5star + 1, 0, is_guaranteed_5star_pickup # 4星天井リセット
    cumulative_rate += rate_4star_char

    if rand_val < cumulative_rate + rate_4star_lightcone:
        result_item = "4_star_pickup_lightcone"
        return result_item, current_pity_5star + 1, 0, is_guaranteed_5star_pickup # 4星天井リセット
    cumulative_rate += rate_4star_lightcone

    # 3星
    result_item = "3_star_lightcone"
    return result_item, current_pity_5star + 1, current_pity_4star + 1, is_guaranteed_5star_pickup


def calculate_starlight_fragments(item_type, num_5star_pickup_char_obtained, num_5star_other_char_obtained):
    """
    排出されたアイテムに応じて獲得できる「消えない星芒」の数を計算する。
    :param item_type: 排出されたアイテムの種類
    :param num_5star_pickup_char_obtained: 獲得済みのピックアップ☆5キャラ数
    :param num_5star_other_char_obtained: 獲得済みの非ピックアップ☆5キャラ数
    :return: 獲得星芒数
    """
    if item_type == "5_star_pickup_char":
        if 2 <= num_5star_pickup_char_obtained <= 7:
            return STARLIGHT_FRAGMENTS["5_star_pickup_char_2_7"]
        elif num_5star_pickup_char_obtained >= 8:
            return STARLIGHT_FRAGMENTS["5_star_char_8_plus"]
        else: # 1回目
            return 0 # 1回目は星芒なし
    elif item_type == "5_star_other_char":
        if 1 <= num_5star_other_char_obtained <= 7:
            return STARLIGHT_FRAGMENTS["5_star_other_char_1_7"]
        elif num_5star_other_char_obtained >= 8:
            return STARLIGHT_FRAGMENTS["5_star_char_8_plus"]
        else:
            return 0 # 1回目は星芒なし
    elif item_type == "4_star_pickup_char":
        return STARLIGHT_FRAGMENTS["4_star_char"]
    elif item_type == "5_star_pickup_lightcone":
        return STARLIGHT_FRAGMENTS["5_star_lightcone"]
    elif item_type == "5_star_other_lightcone":
        return STARLIGHT_FRAGMENTS["5_star_lightcone"] # ピックアップ外の光円錐も同じ星芒数と仮定
    elif item_type == "4_star_pickup_lightcone":
        return STARLIGHT_FRAGMENTS["4_star_lightcone"]
    else: # 3_star_lightcone
        return 0 # 3星は星芒なし

def run_monte_carlo_simulation(
    target_n_char, target_m_lightcone,
    initial_gems, initial_tickets,
    initial_pity_5star, initial_is_guaranteed_5star_pickup,
    num_simulations=10000
):
    """
    モンテカルロシミュレーションを実行し、現在のリソースで目標達成できる確率と、
    目標達成までのガチャ回数分布を計算する。
    """
    successful_simulations = 0
    pulls_data_for_distribution = [] # 目標達成できたシミュレーションのガチャ回数と星芒チケットを記録 (分布用)
    starlight_tickets_in_successful_sims = [] # 初期リソース内で目標達成できたシミュレーションの星芒チケット数を記録
    
    # シミュレーション対象のガチャタイプを決定
    gacha_type_char_active = (target_n_char > 0)
    gacha_type_lightcone_active = (target_m_lightcone > 0)

    if not gacha_type_char_active and not gacha_type_lightcone_active:
        return {"error": "目標枚数が設定されていません。"}

    for _ in range(num_simulations):
        # --- 初期リソース内で目標達成できるかのシミュレーション ---
        # 各シミュレーションは独立した状態から開始
        current_pity_5star_char = initial_pity_5star if gacha_type_char_active else 0
        current_pity_5star_lightcone = initial_pity_5star if gacha_type_lightcone_active and not gacha_type_char_active else 0
        
        current_pity_4star_char = 0 
        current_pity_4star_lightcone = 0 
        
        is_guaranteed_5star_pickup_char = initial_is_guaranteed_5star_pickup if gacha_type_char_active else False
        is_guaranteed_5star_pickup_lightcone = initial_is_guaranteed_5star_pickup if gacha_type_lightcone_active and not gacha_type_char_active else False

        num_5star_pickup_char_obtained = 0
        num_5star_other_char_obtained = 0
        num_5star_pickup_lightcone_obtained = 0
        num_5star_other_lightcone_obtained = 0
        total_pulls_this_sim = 0 # このシミュレーションでのガチャ回数
        total_starlight_fragments_this_sim = 0 # このシミュレーションでの星芒
        current_tickets_from_starlight_this_sim = 0 # このシミュレーションで星芒から得たチケット

        # このシミュレーションでのリソース管理 (現在のリソースで目標達成確率計算用)
        current_gems_sim = initial_gems
        current_tickets_sim = initial_tickets

        target_achieved_in_sim_with_initial_resources = False # このシミュレーションで初期リソース内で目標達成できたか

        # リソースがある限りガチャを回す (ユーザーの新しい計算順序)
        while current_tickets_sim > 0 or current_gems_sim >= 160:
            total_pulls_this_sim += 1
            
            # リソース消費
            if current_tickets_sim > 0:
                current_tickets_sim -= 1
            else: # current_gems_sim >= 160
                current_gems_sim -= 160

            # ガチャタイプに応じてシミュレート
            #両方のガチャがアクティブな場合、交互に引くか、どちらかを優先するかなどのロジックが必要
            # ここでは簡略化のため、キャラクターガチャが優先されると仮定
            
            # キャラクターガチャのシミュレーション
            if gacha_type_char_active and (num_5star_pickup_char_obtained < target_n_char):
                item_char, current_pity_5star_char, current_pity_4star_char, is_guaranteed_5star_pickup_char = \
                    simulate_single_pull("character", current_pity_5star_char, current_pity_4star_char, is_guaranteed_5star_pickup_char)
                
                if item_char == "5_star_pickup_char":
                    num_5star_pickup_char_obtained += 1
                elif item_char == "5_star_other_char":
                    num_5star_other_char_obtained += 1
                
                total_starlight_fragments_this_sim += calculate_starlight_fragments(item_char, num_5star_pickup_char_obtained, num_5star_other_char_obtained)

            # 光円錐ガチャのシミュレーション
            if gacha_type_lightcone_active and (num_5star_pickup_lightcone_obtained < target_m_lightcone):
                item_lightcone, current_pity_5star_lightcone, current_pity_4star_lightcone, is_guaranteed_5star_pickup_lightcone = \
                    simulate_single_pull("lightcone", current_pity_5star_lightcone, current_pity_4star_lightcone, is_guaranteed_5star_pickup_lightcone)
                
                if item_lightcone == "5_star_pickup_lightcone":
                    num_5star_pickup_lightcone_obtained += 1
                elif item_lightcone == "5_star_other_lightcone":
                    num_5star_other_lightcone_obtained += 1
                
                total_starlight_fragments_this_sim += calculate_starlight_fragments(item_lightcone, 0, 0) # 光円錐ガチャではキャラの星芒は考慮しない

            # 星芒をチケットに交換 (このシミュレーション内でのみ有効)
            while total_starlight_fragments_this_sim >= 20:
                current_tickets_sim += 1 # 得たチケットをすぐに使えるように加算
                current_tickets_from_starlight_this_sim += 1 # 記録用
                total_starlight_fragments_this_sim -= 20

            # 目標達成判定
            target_char_met = (num_5star_pickup_char_obtained >= target_n_char)
            target_lightcone_met = (num_5star_pickup_lightcone_obtained >= target_m_lightcone)

            if (not gacha_type_char_active or target_char_met) and (not gacha_type_lightcone_active or target_lightcone_met):
                target_achieved_in_sim_with_initial_resources = True
                break # 目標達成したのでループを抜ける

            # 無限ループ防止 (念のため)
            if total_pulls_this_sim > 20000: # 20000回回しても達成できない場合は打ち切り
                break
        
        # シミュレーション終了後の結果記録 (現在のリソースで目標達成できたか)
        if target_achieved_in_sim_with_initial_resources:
            successful_simulations += 1
            starlight_tickets_in_successful_sims.append(current_tickets_from_starlight_this_sim)

        # --- 目標達成までのガチャ回数分布計算用のシミュレーション ---
        # リソース無限と仮定して目標達成まで回し続ける
        # (初期リソースとは独立したシミュレーション) 
        current_pity_5star_char_dist = initial_pity_5star if gacha_type_char_active else 0
        current_pity_5star_lightcone_dist = initial_pity_5star if gacha_type_lightcone_active and not gacha_type_char_active else 0
        
        current_pity_4star_char_dist = 0 
        current_pity_4star_lightcone_dist = 0 
        
        is_guaranteed_5star_pickup_char_dist = initial_is_guaranteed_5star_pickup if gacha_type_char_active else False
        is_guaranteed_5star_pickup_lightcone_dist = initial_is_guaranteed_5star_pickup if gacha_type_lightcone_active and not gacha_type_char_active else False

        num_5star_pickup_char_obtained_dist = 0
        num_5star_other_char_obtained_dist = 0
        num_5star_pickup_lightcone_obtained_dist = 0
        num_5star_other_lightcone_obtained_dist = 0
        total_pulls_dist = 0
        total_starlight_fragments_dist = 0
        current_tickets_from_starlight_dist = 0
        gems_consumed_dist = 0 # このシミュレーションで消費した星玉 (初期星玉は考慮しない)

        while True:
            total_pulls_dist += 1
            gems_consumed_dist += 160 # 1回ガチャを引くごとに160星玉消費と仮定

            # ガチャタイプに応じてシミュレート
            if gacha_type_char_active and (num_5star_pickup_char_obtained_dist < target_n_char):
                item_char, current_pity_5star_char_dist, current_pity_4star_char_dist, is_guaranteed_5star_pickup_char_dist = \
                    simulate_single_pull("character", current_pity_5star_char_dist, current_pity_4star_char_dist, is_guaranteed_5star_pickup_char_dist)
                
                if item_char == "5_star_pickup_char":
                    num_5star_pickup_char_obtained_dist += 1
                elif item_char == "5_star_other_char":
                    num_5star_other_char_obtained_dist += 1
                
                total_starlight_fragments_dist += calculate_starlight_fragments(item_char, num_5star_pickup_char_obtained_dist, num_5star_other_char_obtained_dist)

            if gacha_type_lightcone_active and (num_5star_pickup_lightcone_obtained_dist < target_m_lightcone):
                item_lightcone, current_pity_5star_lightcone_dist, current_pity_4star_lightcone_dist, is_guaranteed_5star_pickup_lightcone_dist = \
                    simulate_single_pull("lightcone", current_pity_5star_lightcone_dist, current_pity_4star_lightcone_dist, is_guaranteed_5star_pickup_lightcone_dist)
                
                if item_lightcone == "5_star_pickup_lightcone":
                    num_5star_pickup_lightcone_obtained_dist += 1
                elif item_lightcone == "5_star_other_lightcone":
                    num_5star_other_lightcone_obtained_dist += 1
                
                total_starlight_fragments_dist += calculate_starlight_fragments(item_lightcone, 0, 0) 

            while total_starlight_fragments_dist >= 20:
                current_tickets_from_starlight_dist += 1
                total_starlight_fragments_dist -= 20

            target_char_met_dist = (num_5star_pickup_char_obtained_dist >= target_n_char)
            target_lightcone_met_dist = (num_5star_pickup_lightcone_obtained_dist >= target_m_lightcone)

            if (not gacha_type_char_active or target_char_met_dist) and (not gacha_type_lightcone_active or target_lightcone_met_dist):
                pulls_data_for_distribution.append({
                    'pulls': total_pulls_dist,
                    'starlight_tickets_earned': current_tickets_from_starlight_dist,
                    'gems_consumed': gems_consumed_dist - (current_tickets_from_starlight_dist * 160) # 星芒チケット分を差し引く
                })
                break
            
            if total_pulls_dist > 20000: # 無限ループ防止
                break

    # 結果の計算
    success_probability = (successful_simulations / num_simulations) * 100 if num_simulations > 0 else 0

    avg_starlight_tickets_in_successful_sims = np.mean(starlight_tickets_in_successful_sims) if starlight_tickets_in_successful_sims else 0

    pulls_distribution = {}
    if pulls_data_for_distribution:
        pulls_array = np.array([d['pulls'] for d in pulls_data_for_distribution])
        
        percentiles_values = {
            "25%": np.percentile(pulls_array, 25),
            "50%": np.percentile(pulls_array, 50),
            "75%": np.percentile(pulls_array, 75),
            "99%": np.percentile(pulls_array, 99)
        }

        for key, pulls_at_percentile in percentiles_values.items():
            # このパーセンタイルに対応するガチャ回数に近いシミュレーションデータを探し、
            # そのシミュレーションで得られた星芒チケット数と消費星玉を参照する
            closest_data = min(pulls_data_for_distribution, key=lambda x: abs(x['pulls'] - pulls_at_percentile))
            starlight_tickets_earned_at_percentile = closest_data['starlight_tickets_earned']
            gems_consumed_at_percentile = closest_data['gems_consumed']
            
            pulls_distribution[key] = {
                "pulls": float(pulls_at_percentile),
                "gems_consumed": float(gems_consumed_at_percentile),
                "starlight_tickets_earned": float(starlight_tickets_earned_at_percentile)
            }

    return {
        "success_probability": float(success_probability),
        "avg_starlight_tickets_in_successful_sims": float(avg_starlight_tickets_in_successful_sims),
        "pulls_distribution": pulls_distribution
    }


@app.route('/simulate', methods=['POST'])
def simulate():
    data = request.json
    
    target_n_char = data.get('target_n_char', 0)
    target_m_lightcone = data.get('target_m_lightcone', 0)
    initial_gems = data.get('initial_gems', 0)
    initial_tickets = data.get('initial_tickets', 0)
    initial_pity_5star = data.get('initial_pity_5star', 0)
    initial_is_guaranteed_5star_pickup = data.get('initial_is_guaranteed_5star_pickup', False)
    num_simulations = data.get('num_simulations', 10000) # フロントエンドから受け取る

    # シミュレーション実行
    result = run_monte_carlo_simulation(
        target_n_char, target_m_lightcone,
        initial_gems, initial_tickets,
        initial_pity_5star, initial_is_guaranteed_5star_pickup,
        num_simulations # 引数として渡す
    )
    
    return jsonify(result)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
