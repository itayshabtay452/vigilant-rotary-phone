import enum


class VehicleStatus(str, enum.Enum):
    IN_INSPECTION = "in_inspection"
    WAITING_PARTS = "waiting_parts"
    IN_PROGRESS = "in_progress"
    READY = "ready"
