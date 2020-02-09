# for localized messages
from . import _

PROVIDERS = {
	"Joyne_BE": {
		"name": _("Joyne BE"),
		"transponder": {
			"frequency": 11727,
			"symbol_rate": 30000,
			"polarization": 1,
			"fec_inner": 3,
			"orbital_position": 90,
			"system": 1,
			"modulation": 2,
			"roll_off": 2,
			"onid": 0x009e,
			"tsid": 0xc35a,},
		"bat": {
			"descriptor": 0x83,
			"BouquetID": 0x1,},},
	"Joyne_NL": {
		"name": _("Joyne NL"), 
		"transponder": {
			"frequency": 11747,
			"symbol_rate": 30000,
			"polarization": 0,
			"fec_inner": 3,
			"orbital_position": 90,
			"system": 1,
			"modulation": 2,
			"roll_off": 2,
			"onid": 0x009e,
			"tsid": 0xc364,},
		"bat": {
			"descriptor": 0x83,
			"BouquetID": 0x1,},},}
