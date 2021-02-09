from dataclasses import asdict, dataclass, field
from textwrap import dedent
from typing import Dict, Tuple

INDENT = " " * 4


class RavenRenderable:
    def __str__(self):
        return self.to_rv()


@dataclass
class SubBasinsCommandRecord(RavenRenderable):
    """Record to populate RVH :SubBasins command internal table."""

    subbasin_id: int = 0
    name: str = "sub_XXX"
    downstream_id: int = 0
    profile: str = "chn_XXX"
    reach_length: float = 0
    gauged: bool = False

    def to_rv(self):
        d = asdict(self)
        d["reach_length"] = d["reach_length"] if d["reach_length"] else "ZERO-"
        d["gauged"] = int(d["gauged"])
        return " ".join(map(str, d.values()))


@dataclass
class SubBasinsCommand(RavenRenderable):
    """:SubBasins command (RVH)."""

    subbasins: Tuple[SubBasinsCommandRecord] = ()

    template = """
    :SubBasins
        :Attributes   ID NAME DOWNSTREAM_ID PROFILE REACH_LENGTH  GAUGED
        :Units      none none          none    none           km    none
        {subbasin_records}
    :EndSubBasins
    """

    def to_rv(self):
        recs = [f"    {sb}" for sb in self.subbasins]
        return dedent(self.template).format(subbasin_records="\n".join(recs))


@dataclass
class HRUsCommandRecord(RavenRenderable):
    """Record to populate :HRUs command internal table (RVH)."""

    hru_id: int = 0
    area: float = 0  # km^2
    elevation: float = 0  # meters
    latitude: float = 0
    longitude: float = 0
    subbasin_id: int = 0
    land_use_class: str = ""
    veg_class: str = ""
    soil_profile: str = ""
    aquifer_profile: str = ""
    terrain_class: str = ""
    slope: float = 0.0
    aspect: float = 0.0

    def to_rv(self):
        d = asdict(self)
        return " ".join(map(str, d.values()))


@dataclass
class HRUsCommand(RavenRenderable):
    """:HRUs command (RVH)."""

    hrus: Tuple[HRUsCommandRecord] = ()

    template = """
    :HRUs
        :Attributes      AREA  ELEVATION       LATITUDE      LONGITUDE BASIN_ID       LAND_USE_CLASS           VEG_CLASS      SOIL_PROFILE  AQUIFER_PROFILE TERRAIN_CLASS      SLOPE     ASPECT
        :Units            km2          m            deg            deg     none                  none               none              none             none          none        deg       degN
        {hru_records}
    :EndHRUs
    """

    def to_rv(self):
        recs = [f"    {hru}" for hru in self.hrus]
        return dedent(self.template).format(hru_records="\n".join(recs))


@dataclass
class ReservoirCommand(RavenRenderable):
    """:Reservoir command (RVH)."""

    subbasin_id: int = 0
    hru_id: int = 0
    name: str = "Lake_XXX"
    weir_coefficient: float = 0
    crest_width: float = 0
    max_depth: float = 0
    lake_area: float = 0

    template = """
    :Reservoir {name}
        :SubBasinID {subbasin_id}
        :HRUID {hru_id}
        :Type RESROUTE_STANDARD
        :WeirCoefficient {weir_coefficient}
        :CrestWidth {crest_width}
        :MaxDepth {max_depth}
        :LakeArea {lake_area}
    :EndReservoir
    """

    def to_rv(self):
        d = asdict(self)
        return dedent(self.template).format(**d)


@dataclass
class ReservoirList(RavenRenderable):
    """Sequence of :Reservoir commands."""

    reservoirs: Tuple[ReservoirCommand] = ()

    def to_rv(self):
        return "\n\n".join(map(str, self.reservoirs))


@dataclass
class SubBasinGroupCommand(RavenRenderable):
    """:SubBasinGroup command (RVH)."""

    name: str = ""
    subbasin_ids: Tuple[int] = ()

    template = """
    :SubBasinGroup {name}
        {subbasin_ids}
    :EndSubBasinGroup
    """

    def to_rv(self):
        d = asdict(self)
        d["subbasin_ids"] = map(str, self.subbasin_ids)
        return dedent(self.template).format(**d)


@dataclass
class ChannelProfileCommand(RavenRenderable):
    """:ChannelProfile command (RVP)."""

    name: str = "chn_XXX"
    bed_slope: float = 0
    survey_points: Tuple[Tuple[float, float]] = ()
    roughness_zones: Tuple[Tuple[float, float]] = ()

    template = """
    :ChannelProfile {name}
        :Bedslope {bed_slope}
        :SurveyPoints
        {survey_points}
        :EndSurveyPoints
        :RoughnessZones
        {roughness_zones}
        :EndRoughnessZones
    :EndChannelProfile
    """

    def to_rv(self):
        d = asdict(self)
        d["survey_points"] = "\n".join(
            f"{INDENT * 2}{p[0]} {p[1]}" for p in d["survey_points"]
        )
        d["roughness_zones"] = "\n".join(
            f"{INDENT * 2}{z[0]} {z[1]}" for z in d["roughness_zones"]
        )
        return dedent(self.template).format(**d)


@dataclass
class ChannelProfileList:
    channel_profiles: Tuple[ChannelProfileCommand] = ()

    def to_rv(self):
        return "\n\n".join(map(str, self.channel_profiles))


@dataclass
class GridWeightsCommand(RavenRenderable):
    """:GridWeights command."""

    number_hrus: int = 0
    number_grid_cells: int = 0
    data: Tuple[Tuple[int, int, float]] = ()

    template = """
    {indent}:GridWeights
    {indent}    :NumberHRUs {number_hrus}
    {indent}    :NumberGridCells {number_grid_cells}
    {data}
    {indent}:EndGridWeights
    """

    def to_rv(self, indent_level=0):
        indent = INDENT * indent_level
        d = asdict(self)
        d["indent"] = indent
        d["data"] = "\n".join(f"{indent}    {p[0]} {p[1]} {p[2]}" for p in self.data)
        return dedent(self.template).format(**d)


@dataclass
class GriddedForcingCommand(RavenRenderable):
    """:GriddedForcing command (RVT)."""

    name: str = ""
    forcing_type: str = ""
    file_name_nc: str = ""
    var_name_nc: str = ""
    dim_names_nc: Tuple[str, str, str] = ("x", "y", "t")
    grid_weights: GridWeightsCommand = None

    template = """
    :GriddedForcing {name}
        :ForcingType {forcing_type}
        :FileNameNC {file_name_nc}
        :VarNameNC {var_name_nc}
        :DimNamesNC {dim_names_nc}
        {grid_weights}
    :EndGriddedForcing
    """

    def to_rv(self):
        d = asdict(self)
        d["dim_names_nc"] = " ".join(self.dim_names_nc)
        d["grid_weights"] = self.grid_weights
        return dedent(self.template).format(**d)


@dataclass
class HRUStateVariableTableCommandRecord(RavenRenderable):
    index: int = 1
    surface_water: float = 0
    atmosphere: float = 0
    atmos_precip: float = 0
    ponded_water: float = 0
    soil0: float = 0
    soil1: float = 0
    soil2: float = 0
    soil3: float = 0
    snow_temp: float = 0
    snow: float = 0
    snow_cover: float = 0
    aet: float = 0
    convolution0: float = 0
    convolution1: float = 0
    conv_stor0: float = 0
    conv_stor1: float = 0
    conv_stor2: float = 0
    conv_stor3: float = 0
    conv_stor4: float = 0
    conv_stor5: float = 0
    conv_stor6: float = 0
    conv_stor7: float = 0
    conv_stor8: float = 0
    conv_stor9: float = 0
    conv_stor10: float = 0
    conv_stor11: float = 0
    conv_stor12: float = 0
    conv_stor13: float = 0
    conv_stor14: float = 0
    conv_stor15: float = 0
    conv_stor16: float = 0
    conv_stor17: float = 0
    conv_stor18: float = 0
    conv_stor19: float = 0
    conv_stor20: float = 0
    conv_stor21: float = 0
    conv_stor22: float = 0
    conv_stor23: float = 0
    conv_stor24: float = 0
    conv_stor25: float = 0
    conv_stor26: float = 0
    conv_stor27: float = 0
    conv_stor28: float = 0
    conv_stor29: float = 0
    conv_stor30: float = 0
    conv_stor31: float = 0
    conv_stor32: float = 0
    conv_stor33: float = 0
    conv_stor34: float = 0
    conv_stor35: float = 0
    conv_stor36: float = 0
    conv_stor37: float = 0
    conv_stor38: float = 0
    conv_stor39: float = 0
    conv_stor40: float = 0
    conv_stor41: float = 0
    conv_stor42: float = 0
    conv_stor43: float = 0
    conv_stor44: float = 0
    conv_stor45: float = 0
    conv_stor46: float = 0
    conv_stor47: float = 0
    conv_stor48: float = 0
    conv_stor49: float = 0
    conv_stor50: float = 0
    conv_stor51: float = 0
    conv_stor52: float = 0
    conv_stor53: float = 0
    conv_stor54: float = 0
    conv_stor55: float = 0
    conv_stor56: float = 0
    conv_stor57: float = 0
    conv_stor58: float = 0
    conv_stor59: float = 0
    conv_stor60: float = 0
    conv_stor61: float = 0
    conv_stor62: float = 0
    conv_stor63: float = 0
    conv_stor64: float = 0
    conv_stor65: float = 0
    conv_stor66: float = 0
    conv_stor67: float = 0
    conv_stor68: float = 0
    conv_stor69: float = 0
    conv_stor70: float = 0
    conv_stor71: float = 0
    conv_stor72: float = 0
    conv_stor73: float = 0
    conv_stor74: float = 0
    conv_stor75: float = 0
    conv_stor76: float = 0
    conv_stor77: float = 0
    conv_stor78: float = 0
    conv_stor79: float = 0
    conv_stor80: float = 0
    conv_stor81: float = 0
    conv_stor82: float = 0
    conv_stor83: float = 0
    conv_stor84: float = 0
    conv_stor85: float = 0
    conv_stor86: float = 0
    conv_stor87: float = 0
    conv_stor88: float = 0
    conv_stor89: float = 0
    conv_stor90: float = 0
    conv_stor91: float = 0
    conv_stor92: float = 0
    conv_stor93: float = 0
    conv_stor94: float = 0
    conv_stor95: float = 0
    conv_stor96: float = 0
    conv_stor97: float = 0
    conv_stor98: float = 0
    conv_stor99: float = 0

    def to_rv(self):
        return ",".join(map(repr, asdict(self).values()))


@dataclass
class HRUStateVariableTableCommand(RavenRenderable):
    """Initial condition for a given HRU."""

    template = """
    :HRUStateVariableTable
    :Attributes,SURFACE_WATER,ATMOSPHERE,ATMOS_PRECIP,PONDED_WATER,SOIL[0],SOIL[1],SOIL[2],SOIL[3],SNOW_TEMP,SNOW,SNOW_COVER,AET,CONVOLUTION[0],CONVOLUTION[1],CONV_STOR[0],CONV_STOR[1],CONV_STOR[2],CONV_STOR[3],CONV_STOR[4],CONV_STOR[5],CONV_STOR[6],CONV_STOR[7],CONV_STOR[8],CONV_STOR[9],CONV_STOR[10],CONV_STOR[11],CONV_STOR[12],CONV_STOR[13],CONV_STOR[14],CONV_STOR[15],CONV_STOR[16],CONV_STOR[17],CONV_STOR[18],CONV_STOR[19],CONV_STOR[20],CONV_STOR[21],CONV_STOR[22],CONV_STOR[23],CONV_STOR[24],CONV_STOR[25],CONV_STOR[26],CONV_STOR[27],CONV_STOR[28],CONV_STOR[29],CONV_STOR[30],CONV_STOR[31],CONV_STOR[32],CONV_STOR[33],CONV_STOR[34],CONV_STOR[35],CONV_STOR[36],CONV_STOR[37],CONV_STOR[38],CONV_STOR[39],CONV_STOR[40],CONV_STOR[41],CONV_STOR[42],CONV_STOR[43],CONV_STOR[44],CONV_STOR[45],CONV_STOR[46],CONV_STOR[47],CONV_STOR[48],CONV_STOR[49],CONV_STOR[50],CONV_STOR[51],CONV_STOR[52],CONV_STOR[53],CONV_STOR[54],CONV_STOR[55],CONV_STOR[56],CONV_STOR[57],CONV_STOR[58],CONV_STOR[59],CONV_STOR[60],CONV_STOR[61],CONV_STOR[62],CONV_STOR[63],CONV_STOR[64],CONV_STOR[65],CONV_STOR[66],CONV_STOR[67],CONV_STOR[68],CONV_STOR[69],CONV_STOR[70],CONV_STOR[71],CONV_STOR[72],CONV_STOR[73],CONV_STOR[74],CONV_STOR[75],CONV_STOR[76],CONV_STOR[77],CONV_STOR[78],CONV_STOR[79],CONV_STOR[80],CONV_STOR[81],CONV_STOR[82],CONV_STOR[83],CONV_STOR[84],CONV_STOR[85],CONV_STOR[86],CONV_STOR[87],CONV_STOR[88],CONV_STOR[89],CONV_STOR[90],CONV_STOR[91],CONV_STOR[92],CONV_STOR[93],CONV_STOR[94],CONV_STOR[95],CONV_STOR[96],CONV_STOR[97],CONV_STOR[98],CONV_STOR[99]
        :Units,mm,mm,mm,mm,mm,mm,mm,mm,C,mm,0-1,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm,mm
        {hru_states}
    :EndHRUStateVariableTable
    """
    hru_states: Dict[int, HRUStateVariableTableCommandRecord] = field(
        default_factory=dict
    )

    def to_rv(self):
        return dedent(self.template).format(
            hru_states="\n".join(map(str, self.hru_states.values()))
        )


@dataclass
class BasinIndexCommand(RavenRenderable):
    """Initial conditions for a flow segment."""

    template = """
    :BasinIndex {index},{name}
        :ChannelStorage, {channelstorage}
        :RivuletStorage, {rivuletstorage}
        :Qout,{nsegs},{qout},{qoutlast}
        :Qlat,{nQlatHist},{qlat},{qlatlast}
        :Qin ,{nQinHist}, {qin}
        """

    index: int = 1
    name: str = "watershed"
    channelstorage: float = 0
    rivuletstorage: float = 0
    qout: tuple = (0,)
    qoutlast: float = 0
    qlat: tuple = (0, 0, 0)
    qlatlast: float = 0
    qin: tuple = 20 * (0,)

    def to_rv(self):
        return (
            dedent(self.template)
            .format(
                **asdict(self),
                nsegs=len(self.qout),
                nQlatHist=len(self.qlat),
                nQinHist=len(self.qin),
            )
            .replace("(", "")
            .replace(")", "")
        )


@dataclass
class BasinStateVariablesCommand(RavenRenderable):

    template = """
    :BasinStateVariables
        {basin_states_list}
    :EndBasinStateVariables
    """

    basin_states: Dict[int, BasinIndexCommand] = field(default_factory=dict)

    def to_rv(self):
        return dedent(self.template).format(
            basin_states_list="\n".join(map(str, self.basin_states.values()))
        )
