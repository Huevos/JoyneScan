# for localized messages
from . import _
from enigma import eDVBFrontendParametersSatellite

PROVIDERS = {
	"Joyne_BE": {
		"name": _("Joyne BE"),
		"transponder": {
			"frequency": 11727000,
			"symbol_rate": 30000000,
			"polarization": eDVBFrontendParametersSatellite.Polarisation_Vertical,
			"fec_inner": eDVBFrontendParametersSatellite.FEC_3_4,
			"orbital_position": 90,
			"system": eDVBFrontendParametersSatellite.System_DVB_S2,
			"modulation": eDVBFrontendParametersSatellite.Modulation_8PSK,
			"roll_off": eDVBFrontendParametersSatellite.RollOff_alpha_0_20,
			"original_network_id": 0x009e,
			"transport_stream_id": 0xc35a,},
		"bat": {
			"BouquetID": 0x1,},},
	"Joyne_NL": {
		"name": _("Joyne NL"), 
		"transponder": {
			"frequency": 11747000,
			"symbol_rate": 30000000,
			"polarization": eDVBFrontendParametersSatellite.Polarisation_Horizontal,
			"fec_inner": eDVBFrontendParametersSatellite.FEC_3_4,
			"orbital_position": 90,
			"system": eDVBFrontendParametersSatellite.System_DVB_S2,
			"modulation": eDVBFrontendParametersSatellite.Modulation_8PSK,
			"roll_off": eDVBFrontendParametersSatellite.RollOff_alpha_0_20,
			"original_network_id": 0x009e,
			"transport_stream_id": 0xc364,},
		"bat": {
			"BouquetID": 0x1,},},}
