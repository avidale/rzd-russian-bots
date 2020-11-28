from tgalice.cascade import DialogTurn, Cascade


class RzdTurn(DialogTurn):
    pass


csc = Cascade()


class SLOTS:
    FROM_TEXT = 'from_text'
    TO_TEXT = 'to_text'
    WHEN_TEXT = 'when_text'


TRANSIENT_SLOTS = {
    SLOTS.FROM_TEXT,
    SLOTS.TO_TEXT,
    SLOTS.WHEN_TEXT,
}
