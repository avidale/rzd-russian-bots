from tgalice.nlu.basic_nlu import PYMORPHY


def with_number(noun, number):
    text = agree_with_number(noun=noun, number=number)
    return f'{number} {text}'


def agree_with_number(noun, number):
    last = abs(number) % 10
    tens = abs(number) % 100 // 10
    if PYMORPHY:
        parses = PYMORPHY.parse(noun)
        if parses:
            return parses[0].make_agree_with_number(abs(number)).word
    # detect conjugation based on the word ending
    if last == 1:
        return noun
    elif noun.endswith('ка'):
        if last in {2, 3, 4}:
            return noun[:-1] + 'и'
        else:
            return noun[:-1] + 'ек'
    elif noun.endswith('а'):
        if last in {2, 3, 4}:
            return noun[:-1] + 'ы'
        else:
            return noun[:-1]
    else:
        if last in {2, 3, 4}:
            return noun + 'а'
        else:
            return noun + 'ов'
