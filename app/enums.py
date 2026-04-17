import enum


class VehicleStatus(str, enum.Enum):
    ticket_opened = "ticket_opened"
    mechanics = "mechanics"
    in_test = "in_test"
    washing = "washing"
    ready_for_payment = "ready_for_payment"
    ready = "ready"


class TreatmentReason(str, enum.Enum):
    annual = "annual"
    accident = "accident"
    bodywork = "bodywork"
    diagnostics = "diagnostics"
