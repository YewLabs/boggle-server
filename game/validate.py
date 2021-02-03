# TODO: make this eventually False
ASSERT_VALID = False

class Validator:
    @staticmethod
    def raise_assert():
        if ASSERT_VALID:
            raise Exception('validation error')

    @staticmethod
    def is_nat_str(x):
        if not Validator.is_str(x):
            Validator.raise_assert()
            return False
        if not x.isdigit():
            Validator.raise_assert()
            return False
        return True

    @staticmethod
    def is_nat(x, ub=None):
        if type(x) != int or x < 0:
            Validator.raise_assert()
            return False
        if ub is not None and x >= ub:
            Validator.raise_assert()
            return False
        return True

    def is_dict(x):
        if type(x) != dict:
            Validator.raise_assert()
            return False
        return True

    def has_key(x, k):
        if k not in x:
            Validator.raise_assert()
            return False
        return True

    def is_str(x):
        if type(x) != str:
            Validator.raise_assert()
            return False
        return True

    def is_bool(x):
        if type(x) != bool:
            Validator.raise_assert()
            return False
        return True

