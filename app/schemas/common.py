from pydantic import AfterValidator


def bounded(label: str, min_len: int, max_len: int) -> AfterValidator:
    def check(v: str) -> str:
        v = v.strip()
        if len(v) < min_len:
            raise ValueError(f"{label}: use ao menos {min_len} caracteres")
        if len(v) > max_len:
            raise ValueError(f"{label}: use no máximo {max_len} caracteres")
        return v

    return AfterValidator(check)