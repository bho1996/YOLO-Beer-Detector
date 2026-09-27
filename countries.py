"""
Prefissi telefonici -> nazione + normalizzazione identità.
Nessuna modifica al DB: tutto avviene a runtime.
"""
import re

# Codice -> etichetta con bandiera
COUNTRY_BY_CODE = {
    '+7': '🇷🇺 Russia/KZ',
    '+1': '🇺🇸/🇨🇦 Americas',
    '+212': '🇲🇦 Morocco',
    '+213': '🇩🇿 Algeria',
    '+216': '🇹🇳 Tunisia',
    '+218': '🇱🇾 Libya',
    '+220': '🇬🇲 Gambia',
    '+221': '🇸🇳 Senegal',
    '+222': '🇲🇷 Mauritania',
    '+223': '🇲🇱 Mali',
    '+224': '🇬🇳 Guinea',
    '+225': '🇨🇮 Ivory Coast',
    '+226': '🇧🇫 Burkina Faso',
    '+227': '🇳🇪 Niger',
    '+228': '🇹🇬 Togo',
    '+229': '🇧🇯 Benin',
    '+230': '🇲🇺 Mauritius',
    '+231': '🇱🇷 Liberia',
    '+232': '🇸🇱 Sierra Leone',
    '+233': '🇬🇭 Ghana',
    '+234': '🇳🇬 Nigeria',
    '+235': '🇹🇩 Chad',
    '+237': '🇨🇲 Cameroon',
    '+238': '🇨🇻 Cape Verde',
    '+240': '🇬🇶 Eq. Guinea',
    '+241': '🇬🇦 Gabon',
    '+242': '🇨🇬 Congo',
    '+243': '🇨🇩 DR Congo',
    '+244': '🇦🇴 Angola',
    '+249': '🇸🇩 Sudan',
    '+250': '🇷🇼 Rwanda',
    '+251': '🇪🇹 Ethiopia',
    '+252': '🇸🇴 Somalia',
    '+253': '🇩🇯 Djibouti',
    '+254': '🇰🇪 Kenya',
    '+255': '🇹🇿 Tanzania',
    '+256': '🇺🇬 Uganda',
    '+257': '🇧🇮 Burundi',
    '+258': '🇲🇿 Mozambique',
    '+260': '🇿🇲 Zambia',
    '+261': '🇲🇬 Madagascar',
    '+263': '🇿🇼 Zimbabwe',
    '+264': '🇳🇦 Namibia',
    '+265': '🇲🇼 Malawi',
    '+266': '🇱🇸 Lesotho',
    '+267': '🇧🇼 Botswana',
    '+268': '🇸🇿 Eswatini',
    '+350': '🇬🇮 Gibraltar',
    '+351': '🇵🇹 Portugal',
    '+352': '🇱🇺 Luxembourg',
    '+353': '🇮🇪 Ireland',
    '+354': '🇮🇸 Iceland',
    '+355': '🇦🇱 Albania',
    '+356': '🇲🇹 Malta',
    '+357': '🇨🇾 Cyprus',
    '+358': '🇫🇮 Finland',
    '+359': '🇧🇬 Bulgaria',
    '+370': '🇱🇹 Lithuania',
    '+371': '🇱🇻 Latvia',
    '+372': '🇪🇪 Estonia',
    '+373': '🇲🇩 Moldova',
    '+374': '🇦🇲 Armenia',
    '+375': '🇧🇾 Belarus',
    '+380': '🇺🇦 Ukraine',
    '+381': '🇷🇸 Serbia',
    '+382': '🇲🇪 Montenegro',
    '+383': '🇽🇰 Kosovo',
    '+385': '🇭🇷 Croatia',
    '+386': '🇸🇮 Slovenia',
    '+387': '🇧🇦 Bosnia',
    '+389': '🇲🇰 N. Macedonia',
    '+420': '🇨🇿 Czech Rep.',
    '+421': '🇸🇰 Slovakia',
    '+501': '🇧🇿 Belize',
    '+502': '🇬🇹 Guatemala',
    '+503': '🇸🇻 El Salvador',
    '+504': '🇭🇳 Honduras',
    '+505': '🇳🇮 Nicaragua',
    '+506': '🇨🇷 Costa Rica',
    '+507': '🇵🇦 Panama',
    '+509': '🇭🇹 Haiti',
    '+591': '🇧🇴 Bolivia',
    '+592': '🇬🇾 Guyana',
    '+593': '🇪🇨 Ecuador',
    '+595': '🇵🇾 Paraguay',
    '+597': '🇸🇷 Suriname',
    '+598': '🇺🇾 Uruguay',
    '+670': '🇹🇱 Timor-Leste',
    '+673': '🇧🇳 Brunei',
    '+675': '🇵🇬 Papua N.G.',
    '+676': '🇹🇴 Tonga',
    '+679': '🇫🇯 Fiji',
    '+852': '🇭🇰 Hong Kong',
    '+853': '🇲🇴 Macau',
    '+855': '🇰🇭 Cambodia',
    '+856': '🇱🇦 Laos',
    '+880': '🇧🇩 Bangladesh',
    '+886': '🇹🇼 Taiwan',
    '+960': '🇲🇻 Maldives',
    '+961': '🇱🇧 Lebanon',
    '+962': '🇯🇴 Jordan',
    '+963': '🇸🇾 Syria',
    '+964': '🇮🇶 Iraq',
    '+965': '🇰🇼 Kuwait',
    '+966': '🇸🇦 Saudi Arabia',
    '+967': '🇾🇪 Yemen',
    '+968': '🇴🇲 Oman',
    '+970': '🇵🇸 Palestine',
    '+971': '🇦🇪 UAE',
    '+972': '🇮🇱 Israel',
    '+973': '🇧🇭 Bahrain',
    '+974': '🇶🇦 Qatar',
    '+975': '🇧🇹 Bhutan',
    '+976': '🇲🇳 Mongolia',
    '+977': '🇳🇵 Nepal',
    '+992': '🇹🇯 Tajikistan',
    '+993': '🇹🇲 Turkmenistan',
    '+994': '🇦🇿 Azerbaijan',
    '+995': '🇬🇪 Georgia',
    '+996': '🇰🇬 Kyrgyzstan',
    '+998': '🇺🇿 Uzbekistan',
    '+20': '🇪🇬 Egypt',
    '+27': '🇿🇦 South Africa',
    '+30': '🇬🇷 Greece',
    '+31': '🇳🇱 Netherlands',
    '+32': '🇧🇪 Belgium',
    '+33': '🇫🇷 France',
    '+34': '🇪🇸 Spain',
    '+36': '🇭🇺 Hungary',
    '+39': '🇮🇹 Italy',
    '+40': '🇷🇴 Romania',
    '+41': '🇨🇭 Switzerland',
    '+43': '🇦🇹 Austria',
    '+44': '🇬🇧 UK',
    '+45': '🇩🇰 Denmark',
    '+46': '🇸🇪 Sweden',
    '+47': '🇳🇴 Norway',
    '+48': '🇵🇱 Poland',
    '+49': '🇩🇪 Germany',
    '+51': '🇵🇪 Peru',
    '+52': '🇲🇽 Mexico',
    '+53': '🇨🇺 Cuba',
    '+54': '🇦🇷 Argentina',
    '+55': '🇧🇷 Brazil',
    '+56': '🇨🇱 Chile',
    '+57': '🇨🇴 Colombia',
    '+58': '🇻🇪 Venezuela',
    '+60': '🇲🇾 Malaysia',
    '+61': '🇦🇺 Australia',
    '+62': '🇮🇩 Indonesia',
    '+63': '🇵🇭 Philippines',
    '+64': '🇳🇿 New Zealand',
    '+65': '🇸🇬 Singapore',
    '+66': '🇹🇭 Thailand',
    '+81': '🇯🇵 Japan',
    '+82': '🇰🇷 South Korea',
    '+84': '🇻🇳 Vietnam',
    '+86': '🇨🇳 China',
    '+90': '🇹🇷 Turkey',
    '+91': '🇮🇳 India',
    '+92': '🇵🇰 Pakistan',
    '+93': '🇦🇫 Afghanistan',
    '+94': '🇱🇰 Sri Lanka',
    '+95': '🇲🇲 Myanmar',
    '+98': '🇮🇷 Iran',
}

# Codici internazionali validi (stessa lista del bot.js), usati per capire
# quali prefissi sono "troncati" da vecchie versioni del bot (es. "+12", "+97").
VALID_CODES = set("""
+1242 +1246 +1264 +1268 +1284 +1340 +1345 +1441 +1473 +1649 +1664 +1670 +1671
+1684 +1758 +1767 +1784 +1809 +1829 +1849 +1868 +1869 +1876
+212 +213 +216 +218 +220 +221 +222 +223 +224 +225 +226 +227 +228 +229 +230
+231 +232 +233 +234 +235 +236 +237 +238 +239 +240 +241 +242 +243 +244 +245
+246 +247 +248 +249 +250 +251 +252 +253 +254 +255 +256 +257 +258 +260 +261
+262 +263 +264 +265 +266 +267 +268 +269 +290 +291 +297 +298 +299
+350 +351 +352 +353 +354 +355 +356 +357 +358 +359 +370 +371 +372 +373 +374
+375 +376 +377 +378 +379 +380 +381 +382 +383 +385 +386 +387 +388 +389
+420 +421 +423 +500 +501 +502 +503 +504 +505 +506 +507 +508 +509
+590 +591 +592 +593 +594 +595 +596 +597 +598 +599
+670 +672 +673 +674 +675 +676 +677 +678 +679 +680 +681 +682 +683 +685 +686
+687 +688 +689 +690 +691 +692 +850 +852 +853 +855 +856 +880 +886
+960 +961 +962 +963 +964 +965 +966 +967 +968 +970 +971 +972 +973 +974 +975
+976 +977 +992 +993 +994 +995 +996 +998
+20 +27 +30 +31 +32 +33 +34 +36 +39 +40 +41 +43 +44 +45 +46 +47 +48 +49
+51 +52 +53 +54 +55 +56 +57 +58 +60 +61 +62 +63 +64 +65 +66 +81 +82 +84
+86 +90 +91 +92 +93 +94 +95 +98 +1 +7
""".split())

# Fallback per prefissi troncati che non corrispondono a un paese preciso
REGION_FALLBACK = [
    ('+2', '🌍 Africa (other)'),
    ('+35', '🇪🇺 Europe (other)'),
    ('+37', '🇪🇺 Europe (other)'),
    ('+38', '🇪🇺 Europe (other)'),
    ('+42', '🇪🇺 Europe (other)'),
    ('+5', '🌎 Latin America (other)'),
    ('+6', '🌏 Asia-Pacific (other)'),
    ('+8', '🌏 East Asia (other)'),
    ('+9', '🌏 Middle East / Asia (other)'),
]

_SORTED_CODES = sorted(COUNTRY_BY_CODE, key=len, reverse=True)
_IDENTITY_RE = re.compile(r'^(\+\d+) \*\*\* (\d{4})$')


def get_country(prefix):
    """Restituisce '🇮🇹 Italy' ecc. Gestisce anche prefissi troncati."""
    if prefix is None or prefix != prefix or not str(prefix).strip():  # None / NaN / ''
        return '🏴‍☠️ Unknown'
    prefix = str(prefix).strip()
    for code in _SORTED_CODES:
        if prefix.startswith(code):
            return COUNTRY_BY_CODE[code]
    for code, label in REGION_FALLBACK:
        if prefix.startswith(code):
            return label
    return '🏴‍☠️ Other'


def flag_of(country_label):
    return str(country_label).split(' ')[0] if country_label else '🏴‍☠️'


def build_identity_aliases(user_names):
    """
    Vecchie versioni del bot salvavano il prefisso troncato/esteso a 2 cifre
    (es. '+12 *** 9690' invece di '+1 *** 9690', '+97 *** 6853' invece di
    '+971 *** 6853'). Qui uniamo le identità con le stesse ultime 4 cifre
    quando una ha un prefisso NON valido e l'altra ha il prefisso valido
    "compatibile" (uno è prefisso dell'altro).
    Ritorna {nome_alias: nome_canonico}. Non tocca il DB.
    """
    by_last4 = {}
    for name in user_names:
        m = _IDENTITY_RE.match(str(name).strip())
        if m:
            by_last4.setdefault(m.group(2), []).append((m.group(1), str(name)))

    aliases = {}
    for _, entries in by_last4.items():
        valid = [(p, n) for p, n in entries if p in VALID_CODES]
        invalid = [(p, n) for p, n in entries if p not in VALID_CODES]
        for p_bad, n_bad in invalid:
            candidates = [(p, n) for p, n in valid if p.startswith(p_bad) or p_bad.startswith(p)]
            if len(candidates) == 1:  # solo se non ambiguo
                aliases[n_bad] = candidates[0][1]
    return aliases
