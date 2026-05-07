GSTIN_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
MULTIPLIERS = [1, 2, 1, 2, 1, 2, 4, 1, 2, 1, 2, 4, 1, 2]

pans = [
    ('07', 'AAAPA1234A'),
    ('09', 'AABBB5678B'),
    ('27', 'AACCC9012C'),
    ('33', 'AADDD3456D'),
    ('19', 'AAEEE7890E'),
]

for state, pan in pans:
    for entity in 'Z1A2B3C4D5E6F7G8H9IJKLMNOPQRSTUVWXY':
        prefix = state + pan + entity
        if len(prefix) != 14:
            continue
        total = 0
        for i, char in enumerate(prefix):
            value = GSTIN_CHARS.index(char)
            product = value * MULTIPLIERS[i]
            total += (product // 10) + (product % 10)
        check_digit = GSTIN_CHARS[(10 - (total % 10)) % 10]
        gstin = prefix + check_digit
        # Verify
        total = 0
        for i, char in enumerate(gstin[:14]):
            value = GSTIN_CHARS.index(char)
            product = value * MULTIPLIERS[i]
            total += (product // 10) + (product % 10)
        verify = GSTIN_CHARS[(10 - (total % 10)) % 10]
        if verify == gstin[14]:
            print(f'{pan}: {gstin}')
            break
