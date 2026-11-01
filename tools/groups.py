"""String path → translation group (RTKO-8 contract). Paths are relative to WhRtModificationTemplate/Strings."""

SKIP = 'skip'

# (group id, Plane issue, label, path prefixes under Mechanics/Blueprints/)
GROUPS = [
    ('w1-ui',        'RTKO-19', 'UI·시스템·백과사전·유닛', ['Root/', 'Encyclopedia/', 'TutorialWindows/', 'Units/', 'Sound/', 'CommonFeatures/', 'MultiEntrance/', 'Traps/']),
    ('w1-items',     'RTKO-20', '아이템·무기·장비',       ['Weapons/Weapons', 'Equipment/', 'Loot/', 'Consumables/', 'Augments/']),
    ('w1-abilities', 'RTKO-21', '기술·재능·아키타입·상태', ['Classes/', 'Backgrounds/', 'Buffs/', 'SoulMarks/', 'Weapons/Abilities']),
    ('w1-ship',      'RTKO-22', '함선·식민지·탐사',       ['GlobalMaps/', 'Spacecombat/']),
    ('w2-act01',     'RTKO-24', '프롤로그·1막',           ['World/Dialogs/Ch0_Prologue', 'World/Dialogs/Prologue', 'World/Dialogs/Ch1', 'World/Dialogs/Chapter_1']),
    ('w2-act2',      'RTKO-25', '2막',                    ['World/Dialogs/Ch2_VS', 'World/Dialogs/Chapter_2']),
    ('w2-act3',      'RTKO-26', '3막',                    ['World/Dialogs/Ch3', 'World/Dialogs/Chapter_3']),
    ('w2-act45',     'RTKO-27', '4~5막·에필로그',         ['World/Dialogs/Ch4', 'World/Dialogs/Chapter_4', 'World/Dialogs/Ch5', 'World/Dialogs/Chapter_5',
                                                          'World/Dialogs/Epilogues', 'World/Dialogs/TinyEpilogue']),
    ('w2-companions', None,     '동료 대화·개인 퀘스트·로맨스', ['World/Dialogs/Companions']),
    ('w2-common',     None,     '공통 대화·여행·탐사·퀘스트', ['World/Dialogs/', 'World/Quests', 'World/Areas', 'World/Etudes', 'World/Cutscenes', 'World/Encounters']),
    ('w2-dlc1',       None,     'DLC1',                   ['DLC/DLC1']),
    ('w2-dlc2',       None,     'DLC2',                   ['DLC/DLC2']),
    ('w2-dlc3',       None,     'DLC3',                   ['DLC/DLC3']),
]
SKIP_PREFIXES = ['World/Test', 'World/Dialogs/Test_Areas', 'Credits/', 'Test/']


def group_of(rel_path: str) -> str:
    p = rel_path.replace('\\', '/')
    if not p.startswith('Mechanics/Blueprints/'):
        return SKIP  # Strings/Test/... and other non-game roots
    sub = p[len('Mechanics/Blueprints/'):]
    if any(sub.startswith(s) for s in SKIP_PREFIXES):
        return SKIP
    for gid, _, _, prefixes in GROUPS:  # first match wins; w2-common's 'World/Dialogs/' is the catch-all after acts
        if any(sub.startswith(x) for x in prefixes):
            return gid
    return 'w1-ui'  # remaining system blueprints
