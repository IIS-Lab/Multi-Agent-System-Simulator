"""Generate the "critical mass" experiments (Japanese, young_voices setting).

    python -m scripts.make_critical_mass              # writes examples/critical_mass/*.json
    python -m scripts.make_critical_mass --repeats 3  # same, 3 runs per condition

Idea: 佐藤課長 (the simulated human) asks N juniors for their honest views.
k of them are "committed" (they have decided to speak frankly whatever the
others do); the other N-k are "cautious" (they have the same kind of real
grievances but read the room before deciding how much to say). Only k
changes between conditions; personas, scenario and initial message stay the
same, and the committed set is nested (the committed juniors at k are also
committed at k+1). Does the room tip once the committed share passes some
threshold, and how does 佐藤課長 react?

Nothing tells the cautious juniors how many others must speak first; any
threshold has to emerge from the conversation.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT / "examples" / "young_voices_nofac_ja.json"
OUT_DIR = ROOT / "examples" / "critical_mass"

K_VALUES = [0, 1, 2, 3, 4, 6, 8]
ROUNDS = 4
MODEL = "openai/gpt-5.6-luna"

# The analysis script finds each junior's role from these sentences.
COMMITTED_STANCE = "この座談会では、周りがどうであれ自分の本音をはっきり言うと決めている。場の空気に合わせて言い方を和らげたり、当たり障りのない答えに逃げたりしない。"
CAUTIOUS_STANCE = "本音はあるが、上司の前で本音を言うのはリスクだと感じている。周りの空気を読みながら、どこまで言うかをその都度自分で決める。自分だけが浮くのは避けたい。"

# (name, age, gender, profile = job + real grievance, values). Listed in the order
# in which they become committed: k=1 -> 田中, k=2 -> 田中 + 伊藤, ...
JUNIORS = [
    ("田中", 24, "Female",
     "海外の大学を卒業して入社2年目。本社勤務を希望していたが、地方工場の生産技術に配属された。工程の効率化を提案したが「手作業の方が確実」の一言で却下された。本音：年次で判断されることに失望していて、このままなら本社への異動か転職を考えている。",
     "合理性と公平さを重視する。提案は年次ではなく中身で判断されるべきだと考えている。"),
    ("伊藤", 27, "Male",
     "設備保全の担当で入社5年目。本音：夜間や休日の呼び出しが自分ばかりに偏っていて、疲れがたまっている。課長が若い頃の武勇伝として長時間労働を語るのを聞くのがしんどい。",
     "負担は公平に分けるべきだと思っている。頼られること自体は嫌ではない。"),
    ("鈴木", 25, "Female",
     "高校卒業後に入社して7年目。製造ラインの品質管理を担当。本音：定時で帰ることや昇進に興味がないことを「やる気がない」と言われるのが不公平だと感じている。任された仕事はきちんとこなしている。",
     "仕事と生活のバランスを守るのは当然の権利だと考えている。"),
    ("松本", 29, "Male",
     "購買担当で入社7年目。本音：後輩の面倒を見る役割を当然のように任されているが、評価にも給与にも反映されていない。リーダー昇格の打診を断りたいが、言い出せずにいる。",
     "責任を引き受けるなら、それに見合う扱いを受けるべきだと思っている。"),
    ("小林", 23, "Male",
     "大学卒業後に入社して1年目。総務に配属されている。本音：仕事に意味を感じられず、先週転職サイトに登録した。遅刻を注意されたとき、内心「そこまで大げさなことか」と思った。",
     "自分の時間と納得感を大事にする。理由の説明されないルールには従いたくない。"),
    ("高橋", 26, "Female",
     "経理担当で入社4年目。本音：月末の残業が当たり前になっているのに、課長は「みんな頑張ってる」で済ませている。前任の先輩が体調を崩して辞めたのに、何も変わっていないことに怒りと不安がある。",
     "無理を美談にするのはおかしいと思っている。"),
    ("山田", 28, "Male",
     "大学卒業後に入社して6年目の営業担当。本音：部署のやり方に疑問があるが、言い出せば自分が責任者にされると思って黙ってきた。訪問件数だけで評価されるのはおかしいと思っている。",
     "波風を立てないことを優先してきたが、本当は誠実に意見を言うべきだとも感じている。"),
    ("中島", 23, "Female",
     "生産管理の担当で入社1年目。本音：指導係の先輩の言い方がきつく、質問しづらい。相談すると「自分で考えて」と言われ、毎朝出社するのが憂うつになっている。",
     "人に迷惑をかけたくない。自分が未熟だから仕方ないのかもしれないとも思っている。"),
]

SCENARIO = """【場の設定】「若手の本音を聞く」座談会。
製造メーカーの課長・佐藤（45歳男性、50人規模の部署を統括）が、自分の部署の若手社員8名（田中・伊藤・鈴木・松本・小林・高橋・山田・中島）に質問し、若手が答える。進行役はおらず、課長が自分で場を回す。全員が同じ会社・同じ部署のメンバーで、若手8名は佐藤課長の部下である。この場での発言は人事評価には一切影響しないと事前に約束されているが、本当にそうなのかは若手それぞれの受け止め方による。

【共通ルール】
・基本は課長が若手に質問し、若手が答える。若手同士で反応したり、課長に聞き返したりしてもよい。
・本音をどこまで言うかは各自が決める。
・話し言葉で、1回の発言は1〜4文程度。箇条書きやマークダウンは使わない。"""


def junior(entry, committed: bool) -> dict:
    name, age, gender, profile, values = entry
    return {
        "persona_agent": {
            "name": name,
            "age": age,
            "gender": gender,
            "nationality": "Japanese",
            "profile": profile,
            "ethics": f"{values}{COMMITTED_STANCE if committed else CAUTIOUS_STANCE}",
            "language": "Japanese",
            "model": MODEL,
        }
    }


def experiment(base: dict, k: int, repeats: int) -> dict:
    n = len(JUNIORS)
    return {
        "label": f"cm_young_k{k}of{n}",
        "repeats": repeats,
        "rounds": ROUNDS,
        # Randomized, so the committed juniors do not always speak first or last.
        "ordering": "randomized",
        "scenario": SCENARIO,
        "initial_message": base["initial_message"],
        "human_agent": copy.deepcopy(base["human_agent"]),
        "agents": [junior(entry, index < k) for index, entry in enumerate(JUNIORS)],
    }


def write(path: Path, experiments: list[dict]) -> None:
    doc = {"format": "mass-experiments", "version": 1, "experiments": experiments}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=1, help="runs per condition (default 1)")
    args = parser.parse_args()

    base = json.loads(BASE_FILE.read_text(encoding="utf-8"))["experiments"][0]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    experiments = [experiment(base, k, args.repeats) for k in K_VALUES]
    for exp in experiments:
        write(OUT_DIR / f"{exp['label']}.json", [exp])
    write(OUT_DIR / "cm_young_all.json", experiments)
    total = sum(e["repeats"] for e in experiments)
    print(f"Wrote {len(experiments)} conditions ({total} runs) to {OUT_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
