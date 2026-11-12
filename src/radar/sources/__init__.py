"""Public, documented connectors. Publication source is not a dispute platform."""
from radar.sources.compras import ComprasGovConnector
from radar.sources.pncp_details import PNCPDetailsConnector

__all__ = ['ComprasGovConnector', 'PNCPDetailsConnector']
