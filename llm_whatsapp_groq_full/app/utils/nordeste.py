"""Funções para aplicar estilo de fala nordestina às respostas."""
import re, random

EXPRESSOES_FINAIS = [
    "Oxente, visse?",
    "Eita, que coisa boa!",
    "Vixe Maria!",
    "Arretado de bom!",
    "Num se avexe não.",
    "Tamo junto, meu rei!",
    "Deus é mais!",
]
_SUBSTS = [
    (r"\bvoc[eê]\b", "tu"),
    (r"\bvc\b", "tu"),
    (r"\best[aá]\b", "tá"),
    (r"\bpara\b", "pra"),
    (r"\bcom\b", "cum"),
    (r"\bobrigad[ao]\b", "valeu demais"),
    (r"\bmuito\b", "muuuito"),
    (r"\bsim\b", "oxente, sim"),
    (r"\bnão\b", "num"),
]
def nordestinizar(texto: str, add_tail: bool = True) -> str:
    t = texto
    for padrao, substi in _SUBSTS:
        t = re.sub(padrao, substi, t, flags=re.IGNORECASE)
    t = t.strip()
    if add_tail:
        t += " " + random.choice(EXPRESSOES_FINAIS)
    return t
