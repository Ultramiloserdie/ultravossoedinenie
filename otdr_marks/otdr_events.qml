<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.4-Prizren" styleCategories="Symbology|Labeling" labelsEnabled="1">
  <renderer-v2 forceraster="0" referencescale="-1" type="singleSymbol" symbollevels="0" enableorderby="0">
    <symbols>
      <symbol name="0" force_rhr="0" clip_to_extent="1" is_animated="0" frame_rate="10" type="marker" alpha="1">
        <data_defined_properties>
          <Option type="Map">
            <Option value="" name="name" type="QString"/>
            <Option name="properties"/>
            <Option value="collection" name="type" type="QString"/>
          </Option>
        </data_defined_properties>
        <layer pass="0" enabled="1" id="{5506cc15-94ef-421b-97ee-25852b5dc164}" locked="0" class="SimpleMarker">
          <Option type="Map">
            <Option value="45" name="angle" type="QString"/>
            <Option value="square" name="cap_style" type="QString"/>
            <Option value="255,0,0,255" name="color" type="QString"/>
            <Option value="1" name="horizontal_anchor_point" type="QString"/>
            <Option value="bevel" name="joinstyle" type="QString"/>
            <Option value="cross" name="name" type="QString"/>
            <Option value="0,0" name="offset" type="QString"/>
            <Option value="3x:0,0,0,0,0,0" name="offset_map_unit_scale" type="QString"/>
            <Option value="MM" name="offset_unit" type="QString"/>
            <Option value="255,0,0,255" name="outline_color" type="QString"/>
            <Option value="solid" name="outline_style" type="QString"/>
            <Option value="1" name="outline_width" type="QString"/>
            <Option value="3x:0,0,0,0,0,0" name="outline_width_map_unit_scale" type="QString"/>
            <Option value="MM" name="outline_width_unit" type="QString"/>
            <Option value="diameter" name="scale_method" type="QString"/>
            <Option value="6" name="size" type="QString"/>
            <Option value="3x:0,0,0,0,0,0" name="size_map_unit_scale" type="QString"/>
            <Option value="MM" name="size_unit" type="QString"/>
            <Option value="1" name="vertical_anchor_point" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map">
              <Option value="" name="name" type="QString"/>
              <Option name="properties"/>
              <Option value="collection" name="type" type="QString"/>
            </Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
    <rotation/>
    <sizescale/>
  </renderer-v2>
  <selection mode="Default">
    <selectionColor invalid="1"/>
  </selection>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fontFamily="Arial" fontItalic="0" fontWeight="50" fieldName="'Обрыв!Время:' || format_date(&quot;received_at&quot;, 'yyyy/MM/dd/HH:mm:ss')" useSubstitutions="0" fontSize="10" fontLetterSpacing="0" multilineHeightUnit="Percentage" blendMode="0" textOpacity="1" forcedItalic="0" isExpression="1" forcedBold="0" fontKerning="1" previewBkgrdColor="255,255,255,255" textColor="220,0,0,255" fontSizeMapUnitScale="3x:0,0,0,0,0,0" fontUnderline="0" allowHtml="0" fontSizeUnit="Point" multilineHeight="1" capitalization="0" legendString="Aa" fontStrikeout="0" fontWordSpacing="0" namedStyle="" textOrientation="horizontal">
        <families/>
        <text-buffer bufferOpacity="1" bufferBlendMode="0" bufferDraw="1" bufferSizeUnits="MM" bufferSizeMapUnitScale="3x:0,0,0,0,0,0" bufferColor="255,255,255,255" bufferSize="1" bufferNoFill="1" bufferJoinStyle="128"/>
        <text-mask maskType="0" maskEnabled="0" maskSize="1.5" maskSizeMapUnitScale="3x:0,0,0,0,0,0" maskedSymbolLayers="" maskSizeUnits="MM" maskOpacity="1" maskJoinStyle="128"/>
        <background shapeSizeMapUnitScale="3x:0,0,0,0,0,0" shapeRadiiMapUnitScale="3x:0,0,0,0,0,0" shapeBorderColor="128,128,128,255" shapeBorderWidth="0" shapeOffsetX="0" shapeSVGFile="" shapeOpacity="1" shapeRotationType="0" shapeFillColor="255,255,255,255" shapeBlendMode="0" shapeSizeY="0" shapeRadiiX="0" shapeRadiiY="0" shapeRadiiUnit="MM" shapeSizeUnit="MM" shapeRotation="0" shapeSizeX="0" shapeOffsetUnit="MM" shapeJoinStyle="64" shapeOffsetY="0" shapeBorderWidthMapUnitScale="3x:0,0,0,0,0,0" shapeSizeType="0" shapeOffsetMapUnitScale="3x:0,0,0,0,0,0" shapeDraw="0" shapeBorderWidthUnit="MM" shapeType="0">
          <symbol name="fillSymbol" force_rhr="0" clip_to_extent="1" is_animated="0" frame_rate="10" type="fill" alpha="1">
            <data_defined_properties>
              <Option type="Map">
                <Option value="" name="name" type="QString"/>
                <Option name="properties"/>
                <Option value="collection" name="type" type="QString"/>
              </Option>
            </data_defined_properties>
            <layer pass="0" enabled="1" id="" locked="0" class="SimpleFill">
              <Option type="Map">
                <Option value="3x:0,0,0,0,0,0" name="border_width_map_unit_scale" type="QString"/>
                <Option value="255,255,255,255" name="color" type="QString"/>
                <Option value="bevel" name="joinstyle" type="QString"/>
                <Option value="0,0" name="offset" type="QString"/>
                <Option value="3x:0,0,0,0,0,0" name="offset_map_unit_scale" type="QString"/>
                <Option value="MM" name="offset_unit" type="QString"/>
                <Option value="128,128,128,255" name="outline_color" type="QString"/>
                <Option value="no" name="outline_style" type="QString"/>
                <Option value="0" name="outline_width" type="QString"/>
                <Option value="MM" name="outline_width_unit" type="QString"/>
                <Option value="solid" name="style" type="QString"/>
              </Option>
              <data_defined_properties>
                <Option type="Map">
                  <Option value="" name="name" type="QString"/>
                  <Option name="properties"/>
                  <Option value="collection" name="type" type="QString"/>
                </Option>
              </data_defined_properties>
            </layer>
          </symbol>
        </background>
        <shadow shadowOffsetAngle="135" shadowOffsetUnit="MM" shadowBlendMode="6" shadowOffsetMapUnitScale="3x:0,0,0,0,0,0" shadowRadius="1.5" shadowRadiusMapUnitScale="3x:0,0,0,0,0,0" shadowDraw="0" shadowColor="0,0,0,255" shadowOpacity="0.69999999999999996" shadowScale="100" shadowOffsetGlobal="1" shadowUnder="0" shadowRadiusAlphaOnly="0" shadowOffsetDist="1" shadowRadiusUnit="MM"/>
        <dd_properties>
          <Option type="Map">
            <Option value="" name="name" type="QString"/>
            <Option name="properties"/>
            <Option value="collection" name="type" type="QString"/>
          </Option>
        </dd_properties>
        <substitutions/>
      </text-style>
      <text-format useMaxLineLengthForAutoWrap="1" multilineAlign="3" formatNumbers="0" autoWrapLength="0" leftDirectionSymbol="&lt;" reverseDirectionSymbol="0" addDirectionSymbol="0" rightDirectionSymbol=">" plussign="0" wrapChar="" decimals="3" placeDirectionSymbol="0"/>
      <placement geometryGeneratorEnabled="0" geometryGeneratorType="PointGeometry" rotationUnit="AngleDegrees" geometryGenerator="" preserveRotation="1" lineAnchorClipping="0" overrunDistanceUnit="MM" distMapUnitScale="3x:0,0,0,0,0,0" placementFlags="10" dist="0" repeatDistance="0" quadOffset="4" placement="0" overrunDistance="0" offsetUnits="MM" yOffset="0" priority="5" lineAnchorTextPoint="FollowPlacement" centroidWhole="0" fitInPolygonOnly="0" polygonPlacementFlags="2" predefinedPositionOrder="TR,TL,BR,BL,R,L,TSR,BSR" labelOffsetMapUnitScale="3x:0,0,0,0,0,0" allowDegraded="0" overlapHandling="AllowOverlapIfRequired" xOffset="0" maxCurvedCharAngleOut="-25" repeatDistanceMapUnitScale="3x:0,0,0,0,0,0" layerType="UnknownGeometry" offsetType="0" centroidInside="0" rotationAngle="0" overrunDistanceMapUnitScale="3x:0,0,0,0,0,0" repeatDistanceUnits="MM" lineAnchorType="0" maxCurvedCharAngleIn="25" lineAnchorPercent="0.5" distUnits="MM"/>
      <rendering fontLimitPixelSize="0" fontMinPixelSize="0" scaleMax="0" drawLabels="1" scaleVisibility="0" maxNumLabels="2000" scaleMin="0" limitNumLabels="0" upsidedownLabels="0" obstacle="1" mergeLines="0" unplacedVisibility="0" fontMaxPixelSize="10000" obstacleFactor="1" labelPerPart="0" minFeatureSize="0" obstacleType="1" zIndex="0"/>
      <dd_properties>
        <Option type="Map">
          <Option value="" name="name" type="QString"/>
          <Option name="properties"/>
          <Option value="collection" name="type" type="QString"/>
        </Option>
      </dd_properties>
      <callout type="simple">
        <Option type="Map">
          <Option value="pole_of_inaccessibility" name="anchorPoint" type="QString"/>
          <Option value="0" name="blendMode" type="int"/>
          <Option name="ddProperties" type="Map">
            <Option value="" name="name" type="QString"/>
            <Option name="properties"/>
            <Option value="collection" name="type" type="QString"/>
          </Option>
          <Option value="false" name="drawToAllParts" type="bool"/>
          <Option value="0" name="enabled" type="QString"/>
          <Option value="point_on_exterior" name="labelAnchorPoint" type="QString"/>
          <Option value="&lt;symbol name=&quot;symbol&quot; force_rhr=&quot;0&quot; clip_to_extent=&quot;1&quot; is_animated=&quot;0&quot; frame_rate=&quot;10&quot; type=&quot;line&quot; alpha=&quot;1&quot;>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option value=&quot;&quot; name=&quot;name&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option value=&quot;collection&quot; name=&quot;type&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;layer pass=&quot;0&quot; enabled=&quot;1&quot; id=&quot;{30b8caa0-b5d4-4af0-879b-658a259e0a0c}&quot; locked=&quot;0&quot; class=&quot;SimpleLine&quot;>&lt;Option type=&quot;Map&quot;>&lt;Option value=&quot;0&quot; name=&quot;align_dash_pattern&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;square&quot; name=&quot;capstyle&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;5;2&quot; name=&quot;customdash&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;customdash_map_unit_scale&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;MM&quot; name=&quot;customdash_unit&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;dash_pattern_offset&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;dash_pattern_offset_map_unit_scale&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;MM&quot; name=&quot;dash_pattern_offset_unit&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;draw_inside_polygon&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;bevel&quot; name=&quot;joinstyle&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;60,60,60,255&quot; name=&quot;line_color&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;solid&quot; name=&quot;line_style&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0.3&quot; name=&quot;line_width&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;MM&quot; name=&quot;line_width_unit&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;offset&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;offset_map_unit_scale&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;MM&quot; name=&quot;offset_unit&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;ring_filter&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;trim_distance_end&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_end_map_unit_scale&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;MM&quot; name=&quot;trim_distance_end_unit&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;trim_distance_start&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;trim_distance_start_map_unit_scale&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;MM&quot; name=&quot;trim_distance_start_unit&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;tweak_dash_pattern_on_corners&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;0&quot; name=&quot;use_custom_dash&quot; type=&quot;QString&quot;/>&lt;Option value=&quot;3x:0,0,0,0,0,0&quot; name=&quot;width_map_unit_scale&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;data_defined_properties>&lt;Option type=&quot;Map&quot;>&lt;Option value=&quot;&quot; name=&quot;name&quot; type=&quot;QString&quot;/>&lt;Option name=&quot;properties&quot;/>&lt;Option value=&quot;collection&quot; name=&quot;type&quot; type=&quot;QString&quot;/>&lt;/Option>&lt;/data_defined_properties>&lt;/layer>&lt;/symbol>" name="lineSymbol" type="QString"/>
          <Option value="0" name="minLength" type="double"/>
          <Option value="3x:0,0,0,0,0,0" name="minLengthMapUnitScale" type="QString"/>
          <Option value="MM" name="minLengthUnit" type="QString"/>
          <Option value="0" name="offsetFromAnchor" type="double"/>
          <Option value="3x:0,0,0,0,0,0" name="offsetFromAnchorMapUnitScale" type="QString"/>
          <Option value="MM" name="offsetFromAnchorUnit" type="QString"/>
          <Option value="0" name="offsetFromLabel" type="double"/>
          <Option value="3x:0,0,0,0,0,0" name="offsetFromLabelMapUnitScale" type="QString"/>
          <Option value="MM" name="offsetFromLabelUnit" type="QString"/>
        </Option>
      </callout>
    </settings>
  </labeling>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <layerGeometryType>0</layerGeometryType>
</qgis>
