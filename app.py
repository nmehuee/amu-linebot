def calc_shipping(total_packs):
    if total_packs >= 12:
        return 0
    elif total_packs >= 10:
        return 125  # ✅ 100 → 125
    elif total_packs >= 7:
        return 150
    else:
        return 175
