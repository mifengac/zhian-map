import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet.heat';
import { 
  Shield, 
  MapPin, 
  Activity, 
  Filter, 
  Plus, 
  Search, 
  Settings, 
  Layers, 
  TrendingUp, 
  Info,
  Database,
  Play,
  Pause,
  ChevronDown,
  RotateCcw,
  Sparkles,
  AlertTriangle,
  X
} from 'lucide-react';
import './App.css';

// 导入高德下载的本地 JSON 资源
import boundaryData from './yunfu_boundary.json';
import policeData from './police_stations.json';



// TypeScript 接口定义
interface DbIncident {
  caseno: string;
  calltime: string;
  lngofcriterion: number;
  latofcriterion: number;
  neworicharasubclass: string;
  newcharasubclass: string;
  cmdid: string;
  cmdname: string;
  dutydeptna: string;
  dutydeptname: string;
  casecontents: string;
  replies: string;
  cjqk_cleaned: string;
  feedback_source: string;
  disposition_result: string;
  data_quality_flag: string;
}

interface CaseTypeItem {
  leixing: string;
  newcharasubclass_list: string[];
  ay_pattern: string;
}

// 警情类型对应的配色方案（降级后样式匹配）
const CASE_TYPE_STYLES: Record<string, { color: string, iconText: string }> = {
  "打架斗殴": { color: "#ef4444", iconText: "殴" },
  "涉黄": { color: "#f59e0b", iconText: "黄" },
  "赌博": { color: "#10b981", iconText: "赌" },
  "街面三类": { color: "#06b6d4", iconText: "街" },
  "人身伤害类": { color: "#8b5cf6", iconText: "伤" },
  "侵犯财产类": { color: "#ec4899", iconText: "财" },
  "扰乱秩序类": { color: "#3b82f6", iconText: "序" },
  "盗窃": { color: "#a855f7", iconText: "盗" },
  "诈骗": { color: "#f43f5e", iconText: "诈" },
  "毒": { color: "#14b8a6", iconText: "毒" },
  "其他": { color: "#64748b", iconText: "他" }
};

// Leaflet 接口扩展
declare module 'leaflet' {
  export function heatLayer(latlngs: any[], options?: any): any;
  export function markerClusterGroup(options?: any): any;
}

// ==========================================
// 坐标转换算法 (WGS-84 / CGCS2000 与 GCJ-02 互转)
// ==========================================
const PI = 3.1415926535897932384626;
const A_SEMI_MAJOR = 6378245.0;
const EE_ECCENTRICITY = 0.00669342162296594323;

const transformLat = (lng: number, lat: number) => {
  let ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng));
  ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0;
  ret += (20.0 * Math.sin(lat * PI) + 40.0 * Math.sin(lat / 3.0 * PI)) * 2.0 / 3.0;
  ret += (160.0 * Math.sin(lat / 12.0 * PI) + 320 * Math.sin(lat * PI / 30.0)) * 2.0 / 3.0;
  return ret;
};

const transformLng = (lng: number, lat: number) => {
  let ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng));
  ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0;
  ret += (20.0 * Math.sin(lng * PI) + 40.0 * Math.sin(lng / 3.0 * PI)) * 2.0 / 3.0;
  ret += (150.0 * Math.sin(lng / 12.0 * PI) + 300.0 * Math.sin(lng / 30.0 * PI)) * 2.0 / 3.0;
  return ret;
};

const wgs84ToGcj02 = (lng: number, lat: number): [number, number] => {
  let dLat = transformLat(lng - 105.0, lat - 35.0);
  let dLng = transformLng(lng - 105.0, lat - 35.0);
  const radLat = lat / 180.0 * PI;
  let magic = Math.sin(radLat);
  magic = 1.0 - EE_ECCENTRICITY * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / ((A_SEMI_MAJOR * (1.0 - EE_ECCENTRICITY)) / (magic * sqrtMagic) * PI);
  dLng = (dLng * 180.0) / (A_SEMI_MAJOR / sqrtMagic * Math.cos(radLat) * PI);
  return [lng + dLng, lat + dLat];
};

const gcj02ToWgs84 = (lng: number, lat: number): [number, number] => {
  let dLat = transformLat(lng - 105.0, lat - 35.0);
  let dLng = transformLng(lng - 105.0, lat - 35.0);
  const radLat = lat / 180.0 * PI;
  let magic = Math.sin(radLat);
  magic = 1.0 - EE_ECCENTRICITY * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / ((A_SEMI_MAJOR * (1.0 - EE_ECCENTRICITY)) / (magic * sqrtMagic) * PI);
  dLng = (dLng * 180.0) / (A_SEMI_MAJOR / sqrtMagic * Math.cos(radLat) * PI);
  return [lng * 2 - (lng + dLng), lat * 2 - (lat + dLat)];
};

const DISTRICTS = {
  city: { name: '云浮市 (全市域)', center: [22.9298, 112.0444] as [number, number], zoom: 12 },
  yuncheng: { name: '云城区', center: [22.9298, 112.0444] as [number, number], zoom: 13 },
  yunan: { name: '云安区', center: [23.0093, 111.9515] as [number, number], zoom: 13 },
  xinxing: { name: '新兴县', center: [22.6974, 112.2307] as [number, number], zoom: 13 },
  yunanxian: { name: '郁南县', center: [23.2303, 111.5332] as [number, number], zoom: 13 },
  luoding: { name: '罗定市', center: [22.7688, 111.5696] as [number, number], zoom: 13 },
};

const CITY_BOUNDS: L.LatLngBoundsExpression = [[22.30, 111.00], [23.40, 112.60]];

function App() {
  const mapRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const clusterGroupRef = useRef<any | null>(null);
  const heatmapLayerRef = useRef<any | null>(null);
  const boundaryLayerRef = useRef<L.FeatureGroup | null>(null);
  const policeLayerRef = useRef<L.LayerGroup | null>(null);
  // 底图故障探测：短时间内瓦片连续失败的时间戳
  const tileErrorTimestampsRef = useRef<number[]>([]);

  // 1. 数据配置
  const [incidents, setIncidents] = useState<DbIncident[]>([]);
  const [configs, setConfigs] = useState<CaseTypeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tileUrl, setTileUrl] = useState<string | null>(null);
  // 底图故障提示：map-config.json 加载失败，或瓦片连续报错超过阈值
  const [mapConfigError, setMapConfigError] = useState<string | null>(null);

  // 2. 状态控制
  const [selectedDistrict, setSelectedDistrict] = useState<keyof typeof DISTRICTS>('city');
  const [searchQuery, setSearchQuery] = useState('');
  
  // 3. 用户指定需求：分类与映射控制
  const [selectedLeixings, setSelectedLeixings] = useState<string[]>([]); // 动态加载后设置
  const [subclassMode, setSubclassMode] = useState<'原始' | '确认'>('确认'); // 默认确认警情
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // 4. 用户指定与设计：时空范围精细研判状态 (如 6 月份以来 21-23点)
  const [startDate, setStartDate] = useState('2026-06-01');
  const [endDate, setEndDate] = useState('2026-07-05');
  const [startHour, setStartHour] = useState<number>(0);
  const [endHour, setEndHour] = useState<number>(23);

  // 5. 用户指定需求：时间轴控制
  const [selectedHour, setSelectedHour] = useState<number | 'all'>('all'); // 全天或某小时
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef<number | null>(null);

  // 6. 数据大屏增强面板
  const [selectedIncident, setSelectedIncident] = useState<DbIncident | null>(null); // 被选中的警情详情
  const [showSchemaModal, setShowSchemaModal] = useState(false); // 字段释义弹窗

  // 7. 图层控制
  const [isHeatmapActive, setIsHeatmapActive] = useState(false);
  const [isClusteringActive, setIsClusteringActive] = useState(true);
  const [showPoliceStations, setShowPoliceStations] = useState(true);
  const [showBoundary, setShowBoundary] = useState(true);
  const [isDarkMap, setIsDarkMap] = useState(true);

  const isGcjMap = true; // 强制启用纠偏
  const getMapLatLng = (lng: number, lat: number): [number, number] => {
    if (!isGcjMap) return [lat, lng];
    const [gcjLng, gcjLat] = wgs84ToGcj02(lng, lat);
    return [gcjLat, gcjLng];
  };

  // 交互打标
  const [isAddMode, setIsAddMode] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [tempLatLng, setTempLatLng] = useState<{ lat: number, lng: number } | null>(null);
  const [newCaseLocation, setNewCaseLocation] = useState('');
  const [newCaseDesc, setNewCaseDesc] = useState('');
  const [newCaseType, setNewCaseType] = useState<string>('打架斗殴');

  // 动态加载数据库的 JSON 数据
  useEffect(() => {
    const fallbackTile = './tiles/gaode/{z}/{x}/{y}.png';
    const MAP_CONFIG_ERROR_MSG = '底图未配置，或 zhian-tiles(:5099) 未启动';
    fetch('./map-config.json')
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(`请求 map-config.json 失败: HTTP ${res.status}`))))
      .then((cfg: { tileUrl?: string }) => {
        if (typeof cfg.tileUrl !== 'string' || !cfg.tileUrl.includes('{z}')) {
          throw new Error('map-config.json 缺少合法的 tileUrl 字段（需包含 {z}/{x}/{y} 占位符）');
        }
        setTileUrl(cfg.tileUrl.replace(/\{host\}/g, window.location.hostname || '127.0.0.1'));
      })
      .catch(err => {
        console.error('[zhian-map] 底图配置加载失败，已退回相对路径兜底：', err);
        setMapConfigError(MAP_CONFIG_ERROR_MSG);
        setTileUrl(fallbackTile);
      });

    Promise.all([
      fetch('./case_type_config.json').then(res => {
        if (!res.ok) throw new Error("加载 case_type_config 失败");
        return res.json();
      }),
      fetch('./incidents.json').then(res => {
        if (!res.ok) throw new Error("加载 incidents 失败");
        return res.json();
      })
    ]).then(([configData, incidentData]) => {
      setConfigs(configData);
      setIncidents(incidentData);
      setSelectedLeixings(configData.map((c: any) => c.leixing));
      if (configData.length > 0) {
        setNewCaseType(configData[0].leixing);
      }
      setLoading(false);
    }).catch(err => {
      console.error("加载离线数据库配置文件异常:", err);
      setLoading(false);
    });
  }, []);

  // 获取特定警情的映射关系配置
  const getStyleForIncident = (incident: DbIncident) => {
    // 寻找该警情所落入的 leixing
    const val = subclassMode === '确认' ? incident.newcharasubclass : incident.neworicharasubclass;
    const cfg = configs.find(c => c.newcharasubclass_list.includes(val));
    return CASE_TYPE_STYLES[cfg?.leixing || "其他"] || CASE_TYPE_STYLES["其他"];
  };

  const getStyleForLeixing = (leixing: string) => {
    return CASE_TYPE_STYLES[leixing] || CASE_TYPE_STYLES["其他"];
  };

  // 1. 初始化地图组件
  useEffect(() => {
    if (mapRef.current || !tileUrl) return;

    // 默认限制在云浮市全市域范围
    const map = L.map('map', {
      center: DISTRICTS.city.center,
      zoom: DISTRICTS.city.zoom,
      minZoom: 12,
      maxZoom: 18,
      maxBounds: CITY_BOUNDS,
      zoomControl: false
    });

    L.control.zoom({ position: 'topright' }).addTo(map);

    // 透明 1x1 像素占位符，用来平滑替代加载失败（404）的瓦片，防止地图上显示裂图图标
    const transparentTile = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

    // 短时间内瓦片连续失败超过阈值，判定底图服务不可用，弹出提示条
    const TILE_ERROR_THRESHOLD = 20;
    const TILE_ERROR_WINDOW_MS = 10000;
    const handleTileError = () => {
      const now = Date.now();
      const timestamps = tileErrorTimestampsRef.current.filter(t => now - t < TILE_ERROR_WINDOW_MS);
      timestamps.push(now);
      tileErrorTimestampsRef.current = timestamps;
      if (timestamps.length >= TILE_ERROR_THRESHOLD) {
        console.error(`[zhian-map] 瓦片连续加载失败 ${timestamps.length} 次（${TILE_ERROR_WINDOW_MS / 1000}s 内），疑似 zhian-tiles(:5099) 未启动或不可达`);
        setMapConfigError('底图未配置，或 zhian-tiles(:5099) 未启动');
      }
    };

    // 1. 全市域中低精度瓦片图层 (12-13 级)
    const lowZoomLayer = L.tileLayer(tileUrl, {
      minZoom: 12,
      maxZoom: 13,
      bounds: [[22.36, 111.05], [23.32, 112.52]], // 限制在全市域
      attribution: '&copy; 云浮市局立体巡防管控底图'
    }).addTo(map);

    lowZoomLayer.on('tileerror', (e: any) => {
      e.tile.src = transparentTile;
      handleTileError();
    });

    // 2. 云城区市中心高精度瓦片图层 (14-18 级)
    const highZoomLayer = L.tileLayer(tileUrl, {
      minZoom: 14,
      maxZoom: 18,
      bounds: [[22.36, 111.05], [23.32, 112.52]], // 全市 14-18 级
      attribution: '&copy; 云浮市局立体巡防管控底图'
    }).addTo(map);

    highZoomLayer.on('tileerror', (e: any) => {
      e.tile.src = transparentTile;
      handleTileError();
    });

    tileLayerRef.current = lowZoomLayer;
    mapRef.current = map;

    // 暗黑滤镜
    const tilePane = map.getPane('tilePane');
    if (tilePane && isDarkMap) {
      tilePane.classList.add('dark-map-tiles');
    }

    clusterGroupRef.current = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 50
    }).addTo(map);

    boundaryLayerRef.current = L.featureGroup().addTo(map);
    policeLayerRef.current = L.layerGroup().addTo(map);

    // 绑定点击打标
    map.on('click', (e: L.LeafletMouseEvent) => {
      const mapContainer = map.getContainer();
      if (mapContainer.classList.contains('add-mode-active')) {
        let finalWgsCoords: [number, number] = [e.latlng.lat, e.latlng.lng];
        if (isGcjMap) {
          const [wgsLng, wgsLat] = gcj02ToWgs84(e.latlng.lng, e.latlng.lat);
          finalWgsCoords = [wgsLat, wgsLng];
        }
        setTempLatLng({ lat: finalWgsCoords[0], lng: finalWgsCoords[1] });
        setShowAddModal(true);
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [tileUrl]);

  // 监听滤镜控制
  useEffect(() => {
    if (!mapRef.current) return;
    const tilePane = mapRef.current.getPane('tilePane');
    if (tilePane) {
      if (isDarkMap) {
        tilePane.classList.add('dark-map-tiles');
      } else {
        tilePane.classList.remove('dark-map-tiles');
      }
    }
  }, [isDarkMap]);

  // 控制打标光标
  useEffect(() => {
    if (!mapRef.current) return;
    const container = mapRef.current.getContainer();
    if (isAddMode) {
      container.classList.add('add-mode-active');
      container.style.cursor = 'crosshair';
    } else {
      container.classList.remove('add-mode-active');
      container.style.cursor = '';
    }
  }, [isAddMode]);

  // 时间轴自动播放控制
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = window.setInterval(() => {
        setSelectedHour(prev => {
          if (prev === 'all') return 0;
          if (prev >= 23) return 0;
          return prev + 1;
        });
      }, 1500);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying]);

  // 渲染边界及警察机构图层
  useEffect(() => {
    if (!mapRef.current || !boundaryLayerRef.current || !policeLayerRef.current) return;

    const boundaryLayer = boundaryLayerRef.current;
    const policeLayer = policeLayerRef.current;

    boundaryLayer.clearLayers();
    policeLayer.clearLayers();

    if (showBoundary) {
      const polylines = (boundaryData as any).districts[0].polyline.split('|');
      polylines.forEach((line: string) => {
        const points = line.split(';').map(p => {
          const [lng, lat] = p.split(',').map(Number);
          return [lat, lng] as [number, number]; 
        });

        L.polyline(points, {
          color: '#ef4444',
          weight: 2,
          opacity: 0.8,
          fillColor: 'rgba(239, 68, 68, 0.04)',
          fill: true
        }).addTo(boundaryLayer);
      });
    }

    if (showPoliceStations) {
      const pois = (policeData as any).pois;
      pois.forEach((poi: any) => {
        const [gcjLng, gcjLat] = poi.location.split(',').map(Number);

        const shieldIconHtml = `
          <div style="
            width: 26px; 
            height: 26px; 
            background: #1e3a8a; 
            border: 2px solid #60a5fa; 
            border-radius: 6px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
          ">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
        `;

        const policeIcon = L.divIcon({
          html: shieldIconHtml,
          className: 'police-station-pin',
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });

        const marker = L.marker([gcjLat, gcjLng], { icon: policeIcon });

        const popupContent = `
          <div style="width: 220px; font-family: sans-serif; color: #f8fafc;">
            <div style="display:flex; align-items:center; gap: 6px; border-bottom: 1px solid rgba(56, 189, 248, 0.2); padding-bottom: 6px; margin-bottom: 8px;">
              <strong style="color: #60a5fa; font-size: 13px;">👮 ${poi.name}</strong>
            </div>
            <div style="font-size: 11px; color:#cbd5e1; margin-bottom: 6px;">
              <span style="color:#64748b;">地址：</span>${poi.address || '暂无详细登记'}
            </div>
            <div style="font-size: 11px; color:#cbd5e1;">
              <span style="color:#64748b;">电话：</span><a href="tel:${poi.tel}" style="color:#60a5fa; text-decoration:none;">📞 ${poi.tel || '110'}</a>
            </div>
          </div>
        `;

        marker.bindPopup(popupContent).addTo(policeLayer);
      });
    }

  }, [showBoundary, showPoliceStations]);

  // 根据用户设定的所有筛选条件，过滤最终在前端显示的警情列表
  const getFilteredIncidents = () => {
    // A. 找出所有选中 leixing 的 subclass 编码
    const activeSubclasses = new Set<string>();
    configs.forEach(c => {
      if (selectedLeixings.includes(c.leixing)) {
        c.newcharasubclass_list.forEach(code => activeSubclasses.add(code));
      }
    });

    return incidents.filter(c => {
      // 1. 警情分类过滤 (根据选中的模式：原始 vs. 确认)
      const targetSubclass = subclassMode === '确认' ? c.newcharasubclass : c.neworicharasubclass;
      if (!activeSubclasses.has(targetSubclass)) return false;

      // 2. 日期范围过滤
      const callDateStr = c.calltime.substring(0, 10);
      if (callDateStr < startDate || callDateStr > endDate) return false;

      // 3. 时段范围与底部分时轴过滤 (分时轴优先级高于时段范围)
      const hour = parseInt(c.calltime.substring(11, 13), 10);
      if (selectedHour !== 'all') {
        if (hour !== selectedHour) return false;
      } else {
        if (hour < startHour || hour > endHour) return false;
      }

      // 3. 关键字模糊搜索
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          c.caseno.toLowerCase().includes(query) ||
          c.casecontents.toLowerCase().includes(query) ||
          (c.cjqk_cleaned && c.cjqk_cleaned.toLowerCase().includes(query)) ||
          c.dutydeptname.toLowerCase().includes(query) ||
          c.cmdname.toLowerCase().includes(query)
        );
      }

      return true;
    });
  };

  const filteredIncidents = getFilteredIncidents();

  // 渲染警情图层
  useEffect(() => {
    if (!mapRef.current || !clusterGroupRef.current) return;

    const map = mapRef.current;
    const clusterGroup = clusterGroupRef.current;

    clusterGroup.clearLayers();

    if (heatmapLayerRef.current) {
      map.removeLayer(heatmapLayerRef.current);
      heatmapLayerRef.current = null;
    }

    const targetLayerForPins = isClusteringActive ? clusterGroup : map;

    // 绘制警情打标点
    filteredIncidents.forEach(c => {
      const style = getStyleForIncident(c);
      
      // GCJ02 空间投影转换
      const [renderedLat, renderedLng] = getMapLatLng(c.lngofcriterion, c.latofcriterion);

      const svgHtml = `
        <svg width="32" height="38" viewBox="0 0 32 38" fill="none" xmlns="http://www.w3.org/2000/svg" style="filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.5));">
          <path d="M16 0C7.16 0 0 7.16 0 16C0 26.5 16 38 16 38C16 38 32 26.5 32 16C32 7.16 24.84 0 16 0ZM16 22C12.68 22 10 19.32 10 16C10 12.68 12.68 10 16 10C19.32 10 22 12.68 22 16C22 19.32 19.32 22 16 22Z" fill="${style.color}" stroke="#ffffff" stroke-width="1.5"/>
          <circle cx="16" cy="16" r="6" fill="#1e293b"/>
          <text x="16" y="16.5" fill="#ffffff" font-size="8" font-family="system-ui" font-weight="900" text-anchor="middle" dominant-baseline="middle">${style.iconText}</text>
        </svg>
      `;

      const customIcon = L.divIcon({
        html: svgHtml,
        className: 'custom-svg-pin',
        iconSize: [32, 38],
        iconAnchor: [16, 38],
        popupAnchor: [0, -35]
      });

      const marker = L.marker([renderedLat, renderedLng], { icon: customIcon });

      const popupContent = `
        <div style="width: 220px; font-family: sans-serif; color: #f8fafc;">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid rgba(56, 189, 248, 0.2); padding-bottom: 6px; margin-bottom: 8px;">
            <strong style="color: ${style.color}; font-size: 13px;">${c.caseno}</strong>
            <span style="font-size: 9px; padding: 1px 4px; border-radius: 4px; background: rgba(56,189,248,0.1); color: #38bdf8; border: 1px solid rgba(56,189,248,0.2)">
              ${c.cmdname}
            </span>
          </div>
          <div style="font-size: 11px; color:#cbd5e1; margin-bottom: 4px;">接警派出所：${c.dutydeptname}</div>
          <div style="font-size: 11px; color:#cbd5e1; margin-bottom: 4px;">时间：${c.calltime}</div>
          <div style="font-size: 11px; color:#cbd5e1; font-weight: bold; margin-bottom: 4px;">管辖区划ID：${c.cmdid}</div>
          <div style="font-size: 11px; background: rgba(15,23,42,0.4); padding: 6px; border-radius: 4px; color: #94a3b8; line-height: 1.4; max-height: 60px; overflow-y: auto;">
            ${c.casecontents}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);
      
      // 点击点标记可以快速触发右侧面板详情查看
      marker.on('click', () => {
        setSelectedIncident(c);
      });

      targetLayerForPins.addLayer(marker);
    });

    // 绘制热力图
    if (isHeatmapActive) {
      const heatPoints = filteredIncidents.map(c => {
        const [mapLat, mapLng] = getMapLatLng(c.lngofcriterion, c.latofcriterion);
        return [mapLat, mapLng, 0.85] as [number, number, number];
      });
      heatmapLayerRef.current = L.heatLayer(heatPoints, {
        radius: 25,
        blur: 15,
        maxZoom: 15,
        gradient: {
          0.4: '#06b6d4',
          0.6: '#fb923c',
          0.85: '#ef4444'
        }
      }).addTo(map);
    }

  }, [filteredIncidents, isHeatmapActive, isClusteringActive]);

  // 行政区划定位
  const handleDistrictChange = (districtKey: keyof typeof DISTRICTS) => {
    setSelectedDistrict(districtKey);
    if (!mapRef.current) return;
    const dist = DISTRICTS[districtKey];
    mapRef.current.flyTo(dist.center, dist.zoom, { animate: true, duration: 1.5 });
  };

  // 定位警情并点亮 Popup 弹窗与右侧面板
  const locateIncident = (c: DbIncident) => {
    setSelectedIncident(c);
    if (!mapRef.current) return;
    const [mapLat, mapLng] = getMapLatLng(c.lngofcriterion, c.latofcriterion);
    const target = L.latLng(mapLat, mapLng);
    const targetZoom = 16;
    mapRef.current.flyTo(target, targetZoom, { animate: true, duration: 1 });
    
    setTimeout(() => {
      if (!mapRef.current) return;
      mapRef.current.eachLayer((layer: any) => {
        if (layer instanceof L.Marker && layer.getLatLng) {
          const latlng = layer.getLatLng();
          if (Math.abs(latlng.lat - mapLat) < 0.0001 && Math.abs(latlng.lng - mapLng) < 0.0001) {
            layer.openPopup();
          }
        }
      });
    }, 1100);
  };

  // 打标提交 (模拟)
  const handleAddCaseSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!tempLatLng) return;

    // 获取当前所选类型的第一子类叶子码
    const matchingCfg = configs.find(c => c.leixing === newCaseType);
    const targetSubclass = matchingCfg?.newcharasubclass_list[0] || "00000000";

    const newCase: DbIncident = {
      caseno: `JQ-${Date.now().toString().slice(-6)}`,
      calltime: new Date().toISOString().replace('T', ' ').substring(0, 19),
      lngofcriterion: tempLatLng.lng,
      latofcriterion: tempLatLng.lat,
      neworicharasubclass: targetSubclass,
      newcharasubclass: targetSubclass,
      cmdid: "445302",
      cmdname: "云城区",
      dutydeptna: "44530201",
      dutydeptname: "新云城派出所",
      casecontents: newCaseLocation + " — " + newCaseDesc,
      replies: `[${new Date().toLocaleDateString()} 12:00:00] 现场自接警。 【结警反馈】处理结果说明：民警到场快速处理完毕。处理结果：现场调解。`,
      cjqk_cleaned: "民警到场快速处理完毕。",
      feedback_source: "自接警情",
      disposition_result: "现场调解",
      data_quality_flag: "有效案情"
    };

    setIncidents(prev => [newCase, ...prev]);
    setShowAddModal(false);
    setTempLatLng(null);
    setIsAddMode(false);

    setNewCaseLocation('');
    setNewCaseDesc('');

    setTimeout(() => {
      locateIncident(newCase);
    }, 500);
  };

  // 统计分析
  const totalCount = filteredIncidents.length;
  
  // 按区域 (cmdname) 分组数据
  const districtStats = filteredIncidents.reduce((acc, curr) => {
    acc[curr.cmdname] = (acc[curr.cmdname] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // 按派出所 (dutydeptname) 分组排序
  const stationStats = filteredIncidents.reduce((acc, curr) => {
    acc[curr.dutydeptname] = (acc[curr.dutydeptname] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  const sortedStations = Object.entries(stationStats)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5); // 取 Top 5

  const qualityStats = filteredIncidents.reduce((acc, curr) => {
    acc[curr.data_quality_flag] = (acc[curr.data_quality_flag] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // 下拉多选切换
  const handleToggleLeixing = (type: string) => {
    setSelectedLeixings(prev => 
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

  return (
    <div className="dashboard-container">
      {/* 动态数据载入遮罩层 */}
      {loading && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          backgroundColor: '#0b0f19',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#38bdf8',
          fontSize: '18px',
          fontWeight: 'bold',
          fontFamily: 'sans-serif',
          gap: '15px',
          zIndex: 99999
        }}>
          <Shield className="pulse-indicator" style={{ width: 40, height: 40 }} />
          <span>正在载入金仓数据库离线警情数据...</span>
        </div>
      )}
      {/* 左侧面板 */}
      <aside className="sidebar">
        <div className="header-box">
          <h1 className="header-title" style={{ justifyContent: 'space-between' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Shield className="pulse-indicator" style={{ width: 22, height: 22, color: '#38bdf8' }} />
              云浮警情大数据研判大屏
            </span>
            <button 
              onClick={() => setShowSchemaModal(true)} 
              title="查看数据库字段释义"
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '4px',
                transition: 'color 0.2s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.color = '#38bdf8'}
              onMouseLeave={(e) => e.currentTarget.style.color = '#64748b'}
            >
              <Database size={18} />
            </button>
          </h1>
          <p className="header-subtitle">
            数据底座: ywdata.zq_kshddpt_dsjfx_jq (金仓V8)
          </p>
        </div>

        <div className="sidebar-content">
          {/* 数据总览 */}
          <section className="card">
            <h3 className="card-title"><Activity size={16} /> 警情综合态势</h3>
            <div className="stats-grid">
              <div className="stat-item stat-item--highlight">
                <div className="stat-val stat-val--total">{totalCount}</div>
                <div className="stat-lbl">当前过滤结果总数</div>
              </div>
              <div className="stat-item">
                <div className="stat-val stat-val--valid">
                  {qualityStats["有效案情"] || 0}
                </div>
                <div className="stat-lbl">高价值有效警情</div>
              </div>
              <div className="stat-item">
                <div className="stat-val stat-val--invalid">
                  {(qualityStats["低质量"] || 0) + (qualityStats["无有效信息"] || 0)}
                </div>
                <div className="stat-lbl">低质/空处置流水</div>
              </div>
            </div>
          </section>

          {/* 核心需求：配置与分类控制 */}
          <section className="card">
            <h3 className="card-title"><Filter size={16} /> 警情映射与类型筛选</h3>

            {/* 多选下拉框控件 */}
            <div className="form-group form-group--dropdown">
              <label>警情性质配置分类 (ywdata.case_type_config)</label>
              <div 
                className="custom-dropdown-trigger"
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              >
                <span>{selectedLeixings.length === configs.length ? "已选择全部类别" : `已选 ${selectedLeixings.length} 个分类`}</span>
                <ChevronDown size={14} style={{ transform: isDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
              </div>
              
              {isDropdownOpen && (
                <div className="custom-dropdown-options">
                  <div className="dropdown-action-bar">
                    <button type="button" onClick={() => setSelectedLeixings(configs.map(c => c.leixing))}>全选</button>
                    <button type="button" onClick={() => setSelectedLeixings([])}>清空</button>
                  </div>
                  {configs.map(c => {
                    const style = getStyleForLeixing(c.leixing);
                    return (
                      <label className="dropdown-option-item" key={c.leixing}>
                        <input 
                          type="checkbox" 
                          checked={selectedLeixings.includes(c.leixing)}
                          onChange={() => handleToggleLeixing(c.leixing)}
                        />
                        <span style={{ color: style.color, marginRight: '6px' }}>■</span>
                        <span>{c.leixing}</span>
                        <span className="subclass-badge">{c.newcharasubclass_list.length} 子类</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* 唯一单选框：原始/确认警情判定 */}
            <div className="form-group">
              <label>映射匹配模式选择</label>
              <div className="radio-group-container">
                <label className={`radio-label-btn ${subclassMode === '原始' ? 'active' : ''}`}>
                  <input 
                    type="radio" 
                    name="subclass_mode" 
                    value="原始" 
                    checked={subclassMode === '原始'}
                    onChange={() => setSubclassMode('原始')}
                  />
                  原始警情编码 (neworicharasubclass)
                </label>
                <label className={`radio-label-btn ${subclassMode === '确认' ? 'active' : ''}`}>
                  <input 
                    type="radio" 
                    name="subclass_mode" 
                    value="确认" 
                    checked={subclassMode === '确认'}
                    onChange={() => setSubclassMode('确认')}
                  />
                  确认警情编码 (newcharasubclass)
                </label>
              </div>
            </div>
          </section>

          {/* 核心需求：时空范围精细研判 */}
          <section className="card">
            <h3 className="card-title"><Settings size={16} style={{ color: '#38bdf8' }} /> 时空范围精细研判</h3>
            
            {/* 日期范围选择 */}
            <div className="form-group">
              <label>日期范围过滤 (年-月-日)</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <input 
                  type="date" 
                  value={startDate} 
                  onChange={(e) => setStartDate(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(51, 65, 85, 0.5)',
                    borderRadius: '4px',
                    color: 'white',
                    padding: '4px 8px',
                    fontSize: '12px'
                  }}
                />
                <span style={{ fontSize: '12px', color: '#64748b' }}>至</span>
                <input 
                  type="date" 
                  value={endDate} 
                  onChange={(e) => setEndDate(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(51, 65, 85, 0.5)',
                    borderRadius: '4px',
                    color: 'white',
                    padding: '4px 8px',
                    fontSize: '12px'
                  }}
                />
              </div>
            </div>

            {/* 时段范围选择 */}
            <div className="form-group">
              <label>接警时段范围 (24小时制)</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <select
                  value={startHour}
                  onChange={(e) => setStartHour(Number(e.target.value))}
                  style={{
                    flex: 1,
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(51, 65, 85, 0.5)',
                    borderRadius: '4px',
                    color: 'white',
                    padding: '4px 8px',
                    fontSize: '12px'
                  }}
                >
                  {Array.from({ length: 24 }).map((_, h) => (
                    <option key={h} value={h}>{h.toString().padStart(2, '0')}:00</option>
                  ))}
                </select>
                <span style={{ fontSize: '12px', color: '#64748b' }}>至</span>
                <select
                  value={endHour}
                  onChange={(e) => setEndHour(Number(e.target.value))}
                  style={{
                    flex: 1,
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(51, 65, 85, 0.5)',
                    borderRadius: '4px',
                    color: 'white',
                    padding: '4px 8px',
                    fontSize: '12px'
                  }}
                >
                  {Array.from({ length: 24 }).map((_, h) => (
                    <option key={h} value={h}>{h.toString().padStart(2, '0')}:59</option>
                  ))}
                </select>
              </div>
            </div>

            {/* 快捷时段过滤 */}
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                className="timeline-btn"
                style={{ flex: 1, fontSize: '11px', padding: '6px 4px', border: '1px solid rgba(56,189,248,0.3)', color: '#38bdf8' }}
                onClick={() => {
                  setStartDate('2026-06-01');
                  setEndDate('2026-07-05');
                  setStartHour(21);
                  setEndHour(23);
                  setSelectedLeixings(['打架斗殴']);
                }}
              >
                🚨 夜间高峰 (6月以来 21-23点)
              </button>
              <button
                type="button"
                className="timeline-btn"
                style={{ flex: 1, fontSize: '11px', padding: '6px 4px', background: 'transparent', border: '1px solid rgba(100,116,139,0.3)' }}
                onClick={() => {
                  setStartDate('2026-06-01');
                  setEndDate('2026-07-05');
                  setStartHour(0);
                  setEndHour(23);
                  setSelectedLeixings(configs.map(c => c.leixing));
                }}
              >
                🔄 恢复全天全期
              </button>
            </div>
          </section>

          {/* 交互打标 */}
          <section className="card">
            <h3 className="card-title"><MapPin size={16} /> 空间警情交互打标</h3>
            <button 
              className={`action-btn ${isAddMode ? 'active' : ''}`}
              onClick={() => setIsAddMode(!isAddMode)}
            >
              {isAddMode ? '取消打标状态' : '手工警情打标'}
              <Plus size={16} />
            </button>
            <p style={{ fontSize: '11px', color: '#64748b', marginTop: '6px', lineHeight: '1.4' }}>
              开启后，在地图任意网格点击左键，可补录标准 CGCS2000 位置坐标的警情。
            </p>
          </section>

          {/* 地区警情热力统计 (Bar Chart by District) */}
          <section className="card">
            <h3 className="card-title"><TrendingUp size={16} /> 地区警情热力统计</h3>
            <div className="custom-chart-container">
              {DISTRICTS.city.center && Object.entries(districtStats).map(([name, count]) => {
                const maxVal = Math.max(...Object.values(districtStats), 1);
                const percent = Math.round((count / maxVal) * 100);
                return (
                  <div className="chart-bar-item" key={name}>
                    <div className="chart-bar-label">{name}</div>
                    <div className="chart-bar-track">
                      <div className="chart-bar-fill" style={{ width: `${percent}%` }}></div>
                    </div>
                    <div className="chart-bar-value">{count}起</div>
                  </div>
                );
              })}
              {Object.keys(districtStats).length === 0 && (
                <div style={{ textAlign: 'center', fontSize: '12px', color: '#64748b', padding: '10px' }}>暂无统计数据</div>
              )}
            </div>
          </section>

          {/* 派出所警情排行榜 */}
          <section className="card">
            <h3 className="card-title"><Shield size={16} /> 派出所警情排行榜 (Top 5)</h3>
            <div className="leaderboard-list">
              {sortedStations.map(([name, count], index) => {
                const topCount = sortedStations[0]?.[1] || 1;
                const percent = Math.round((count / topCount) * 100);
                return (
                  <div className="leaderboard-item" key={name}>
                    <div className="leaderboard-rank">{index + 1}</div>
                    <div className="leaderboard-info">
                      <div className="leaderboard-name">{name}</div>
                      <div className="leaderboard-bar-bg">
                        <div className="leaderboard-bar-fill" style={{ width: `${percent}%` }}></div>
                      </div>
                    </div>
                    <div className="leaderboard-count">{count}起</div>
                  </div>
                );
              })}
              {sortedStations.length === 0 && (
                <div style={{ textAlign: 'center', fontSize: '12px', color: '#64748b', padding: '10px' }}>暂无数据</div>
              )}
            </div>
          </section>
        </div>
      </aside>

      {/* 中部地图工作区 */}
      <main className="map-container">
        <div id="map"></div>

        {/* 底图故障提示：map-config.json 加载失败，或瓦片连续报错超过阈值 */}
        {mapConfigError && (
          <div className="map-config-banner">
            <AlertTriangle size={14} />
            <span>{mapConfigError}</span>
            <button
              className="map-config-banner-close"
              onClick={() => setMapConfigError(null)}
              aria-label="关闭提示"
              title="关闭提示"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* 顶部悬浮控制栏 */}
        <div className="map-overlay-tools">
          <button 
            className={`overlay-btn ${isClusteringActive ? 'active' : ''}`}
            onClick={() => setIsClusteringActive(!isClusteringActive)}
          >
            <Layers size={14} />
            点聚合：{isClusteringActive ? '开' : '关'}
          </button>
          
          <button 
            className={`overlay-btn ${isHeatmapActive ? 'active' : ''}`}
            onClick={() => setIsHeatmapActive(!isHeatmapActive)}
          >
            <Activity size={14} />
            热力图：{isHeatmapActive ? '开' : '关'}
          </button>

          <button 
            className={`overlay-btn ${showPoliceStations ? 'active' : ''}`}
            onClick={() => setShowPoliceStations(!showPoliceStations)}
          >
            <Shield size={14} />
            派出所点位：{showPoliceStations ? '开' : '关'}
          </button>

          <button 
            className={`overlay-btn ${showBoundary ? 'active' : ''}`}
            onClick={() => setShowBoundary(!showBoundary)}
          >
            <MapPin size={14} />
            市域边界：{showBoundary ? '显' : '隐'}
          </button>

          <button 
            className={`overlay-btn ${isDarkMap ? 'active' : ''}`}
            onClick={() => setIsDarkMap(!isDarkMap)}
          >
            <Settings size={14} />
            科技暗黑：{isDarkMap ? '开' : '关'}
          </button>

          <select 
            className="overlay-btn"
            style={{ padding: '0 10px', height: '32px' }}
            value={selectedDistrict}
            onChange={(e) => handleDistrictChange(e.target.value as keyof typeof DISTRICTS)}
          >
            {Object.entries(DISTRICTS).map(([key, item]) => (
              <option key={key} value={key}>{item.name}</option>
            ))}
          </select>
        </div>

        {/* 核心需求：时间轴轴面板 (Timeline Slider) */}
        <div className="timeline-axis-card">
          <div className="timeline-header">
            <div className="timeline-title">
              <Activity size={14} style={{ color: '#38bdf8' }} />
              <span>接警时序分析轴 (全天 24 小时)</span>
            </div>
            <div className="timeline-controls">
              <button 
                className="timeline-btn" 
                onClick={() => setIsPlaying(!isPlaying)}
                title={isPlaying ? "暂停播放" : "开始播放时序轨迹"}
              >
                {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                <span>{isPlaying ? "暂停" : "播放"}</span>
              </button>
              <button 
                className={`timeline-btn ${selectedHour === 'all' ? 'active' : ''}`}
                onClick={() => { setSelectedHour('all'); setIsPlaying(false); }}
              >
                <RotateCcw size={12} />
                全天展示
              </button>
            </div>
          </div>

          <div className="timeline-slider-wrapper">
            <span className="slider-label">00:00</span>
            <input 
              type="range" 
              min="0" 
              max="23" 
              value={selectedHour === 'all' ? 0 : selectedHour} 
              onChange={(e) => { setSelectedHour(Number(e.target.value)); setIsPlaying(false); }}
              className="timeline-slider-input"
              style={{
                opacity: selectedHour === 'all' ? 0.4 : 1
              }}
            />
            <span className="slider-label">23:00</span>
          </div>

          <div className="timeline-indicator">
            <div>
              当前展示: {selectedHour === 'all' ? (
                <span className="time-highlight">全天累计（或左侧设定时空段）</span>
              ) : (
                <span className="time-highlight">{selectedHour.toString().padStart(2, '0')}:00 - {selectedHour.toString().padStart(2, '0')}:59 时段</span>
              )}
            </div>
            <div className="timeline-indicator-right">
              <span className={`time-highlight ${filteredIncidents.length > 0 ? 'time-highlight--ok' : 'time-highlight--empty'}`}>
                当前时段警情: {filteredIncidents.length} 起
              </span>
              {filteredIncidents.length === 0 && (
                <span className="timeline-empty-hint">
                  ⚠️ 该时段暂无符合筛选条件的警情
                </span>
              )}
            </div>
          </div>

          {/* 坐标自适应说明：原来是地图区域左下角单独浮层，和本卡片同高会打架，现并入时间轴卡片内 */}
          <div className="timeline-footnote">
            <Info size={12} style={{ color: '#38bdf8' }} />
            <span>离线底图模式: </span>
            <span className="timeline-footnote-highlight">
              本地高德切片 (已自动开启 CGCS2000 坐标系自适应对齐)
            </span>
          </div>
        </div>

        {/* 打标提示 */}
        {isAddMode && (
          <div className="add-marker-tip">
            🚨 鼠标左键点击地图，即可在点击处补录警情数据
          </div>
        )}

        {/* 交互打标模态框 */}
        {showAddModal && tempLatLng && (
          <div className="modal-overlay">
            <form className="modal-content" onSubmit={handleAddCaseSubmit}>
              <h4 className="modal-title">新增警情打标</h4>
              
              <div className="form-group">
                <label>标准空间经纬度 (CGCS2000 / WGS84)</label>
                <div className="coord-preview">
                  经度: {tempLatLng.lng.toFixed(6)}<br />
                  纬度: {tempLatLng.lat.toFixed(6)}
                </div>
              </div>

              <div className="form-group">
                <label>警情类别 (新子类关联)</label>
                <select 
                  value={newCaseType} 
                  onChange={(e) => setNewCaseType(e.target.value)}
                >
                  {configs.map(c => (
                    <option key={c.leixing} value={c.leixing}>{c.leixing}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>报警地点</label>
                <input 
                  type="text" 
                  placeholder="如：云城区新兴二路188号" 
                  value={newCaseLocation}
                  onChange={(e) => setNewCaseLocation(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label>警情摘要简述</label>
                <textarea 
                  rows={3}
                  placeholder="请输入报警内容及简述..." 
                  value={newCaseDesc}
                  onChange={(e) => setNewCaseDesc(e.target.value)}
                  required
                ></textarea>
              </div>

              <div className="modal-actions">
                <button 
                  type="button" 
                  className="modal-btn cancel" 
                  onClick={() => { setShowAddModal(false); setTempLatLng(null); }}
                >
                  取消
                </button>
                <button 
                  type="submit" 
                  className="modal-btn submit"
                >
                  确认保存
                </button>
              </div>
            </form>
          </div>
        )}
      </main>

      {/* 右侧面板 */}
      <aside className="right-panel">
        {/* 警情实时检索 */}
        <div className="header-box header-box--plain">
          <h3 className="header-title header-title--sm">
            <Search size={18} /> 警情数据流水检索
          </h3>
        </div>

        <div className="search-box">
          <div className="search-input-wrapper">
            <input
              type="text"
              placeholder="搜索警情流水、报警内容、派出所..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="search-input"
            />
            <Search size={14} className="search-input-icon" />
          </div>
        </div>

        {/* 警情列表 */}
        <div className="right-panel-content" style={{ flex: selectedIncident ? '0.4' : '1' }}>
          <div className="alarm-list-container">
            {filteredIncidents.map(c => {
              const style = getStyleForIncident(c);
              return (
                <div 
                  className={`alarm-list-item ${selectedIncident?.caseno === c.caseno ? 'selected' : ''}`}
                  key={c.caseno}
                  onClick={() => locateIncident(c)}
                >
                  <div className="alarm-list-header">
                    <span className="alarm-badge" style={{ backgroundColor: `${style.color}20`, color: style.color, border: `1px solid ${style.color}50` }}>
                      {c.caseno}
                    </span>
                    <span className="alarm-time">{c.calltime.substring(11, 16)}</span>
                  </div>
                  <div className="alarm-desc">{c.casecontents}</div>
                  <div className="alarm-location">
                    <span className="alarm-location-place">
                      <MapPin size={11} style={{ color: '#38bdf8' }} />
                      <span>{c.dutydeptname}</span>
                    </span>
                    <span style={{ fontSize: '10px', color: c.data_quality_flag === '有效案情' ? '#4ade80' : '#f87171' }}>
                      {c.data_quality_flag}
                    </span>
                  </div>
                </div>
              );
            })}
            {filteredIncidents.length === 0 && (
              <div style={{ textAlign: 'center', color: '#64748b', fontSize: '12px', padding: '20px' }}>无符合筛选条件的警情数据</div>
            )}
          </div>
        </div>

        {/* 警情清洗效果对比看板 */}
        {selectedIncident && (
          <div className="cleaned-inspect-panel">
            <div className="inspect-header">
              <Sparkles size={14} style={{ color: '#a855f7' }} />
              <span>警情处警数据清洗与对比看板</span>
            </div>
            
            <div className="inspect-body">
              <div className="inspect-meta-grid">
                <div><span>派出所:</span> {selectedIncident.dutydeptname}</div>
                <div><span>报警时间:</span> {selectedIncident.calltime}</div>
                <div><span>确认子类码:</span> {selectedIncident.newcharasubclass}</div>
                <div><span>原始子类码:</span> {selectedIncident.neworicharasubclass}</div>
              </div>

              {/* 报警内容 */}
              <div className="inspect-section">
                <div className="inspect-section-title">🚨 报警内容 (casecontents)</div>
                <div className="inspect-section-content">{selectedIncident.casecontents}</div>
              </div>

              {/* 处警情况对比 */}
              <div className="inspect-section">
                <div className="inspect-section-title" style={{ color: '#f43f5e' }}>📜 处警原文 (replies)</div>
                <div className="inspect-section-content code-style">{selectedIncident.replies}</div>
              </div>

              <div className="inspect-section" style={{ border: '1px solid rgba(168, 85, 247, 0.3)', background: 'rgba(168, 85, 247, 0.05)' }}>
                <div className="inspect-section-title" style={{ color: '#a855f7' }}>✨ 算法清洗后处警内容 (cjqk_cleaned)</div>
                <div className="inspect-section-content cleaned-style">
                  {selectedIncident.cjqk_cleaned || <span style={{ color: '#64748b', fontStyle: 'italic' }}>无有效反馈段落</span>}
                </div>
              </div>

              <div className="inspect-footer-tags">
                <span className="inspect-tag">来源: {selectedIncident.feedback_source}</span>
                <span className="inspect-tag">处置结果: {selectedIncident.disposition_result || "未知"}</span>
                <span className="inspect-tag" style={{
                  color: selectedIncident.data_quality_flag === '有效案情' ? '#4ade80' : '#f87171',
                  background: selectedIncident.data_quality_flag === '有效案情' ? 'rgba(74,222,128,0.1)' : 'rgba(248,113,113,0.1)'
                }}>
                  标记: {selectedIncident.data_quality_flag}
                </span>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* 字段释义弹窗 (Database Fields Explanation Modal) */}
      {showSchemaModal && (
        <div className="modal-overlay" style={{ zIndex: 10000 }}>
          <div className="modal-content schema-modal">
            <h3 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Database style={{ color: '#38bdf8' }} />
              数据库字段与算法清洗释义手册
            </h3>
            
            <div className="schema-table-wrapper">
              <table className="schema-table">
                <thead>
                  <tr>
                    <th>数据表字段</th>
                    <th>业务对应名称</th>
                    <th>数据特征与处理说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="code-font">cmdid</td>
                    <td>地区编码</td>
                    <td>行政区域 ID（如 `445302` 代表云城区，`445381` 代表罗定市）。</td>
                  </tr>
                  <tr>
                    <td className="code-font">cmdname</td>
                    <td>地区名称</td>
                    <td>该警情发生的市辖区/县名称，用于大屏统计栏横向热力条过滤。</td>
                  </tr>
                  <tr>
                    <td className="code-font">dutydeptna</td>
                    <td>派出所编码</td>
                    <td>具体出警管辖派出所机构的代码，用于细分警力结构。</td>
                  </tr>
                  <tr>
                    <td className="code-font">dutydeptname</td>
                    <td>派出所名称</td>
                    <td>负责出警处置的派出所中文名称，用于派出所排行看板。</td>
                  </tr>
                  <tr>
                    <td className="code-font">casecontents</td>
                    <td>报警内容</td>
                    <td>接警中心记录的报警人叙述原文（包含时间、地点、警情描述简述）。</td>
                  </tr>
                  <tr>
                    <td className="code-font">replies</td>
                    <td>处警情况 (原文)</td>
                    <td>**原始流水字串**。包含 ASCII 日志头、调度日志、结警反馈等多余噪音。不可直接展示。</td>
                  </tr>
                  <tr style={{ background: 'rgba(168, 85, 247, 0.08)' }}>
                    <td className="code-font highlight">cjqk_cleaned</td>
                    <td>清洗后处警内容</td>
                    <td>**算法输出**。经过 clean_replies 脚本去噪后，提取出的真实出警叙述和处理细节。</td>
                  </tr>
                  <tr style={{ background: 'rgba(168, 85, 247, 0.08)' }}>
                    <td className="code-font highlight">feedback_source</td>
                    <td>处警信息来源</td>
                    <td>**算法判定**。提取的来源类型：【结警反馈】、【过程反馈】、不出警原因 或 自接警情。</td>
                  </tr>
                  <tr style={{ background: 'rgba(168, 85, 247, 0.08)' }}>
                    <td className="code-font highlight">disposition_result</td>
                    <td>处置最终结果</td>
                    <td>**算法提取**。从处理结果中提取的简短结论，如：立案侦查、行政拘留等。</td>
                  </tr>
                  <tr style={{ background: 'rgba(168, 85, 247, 0.08)' }}>
                    <td className="code-font highlight">data_quality_flag</td>
                    <td>数据质量标记</td>
                    <td>判定分类：有效案情、低质量、无效警情、外市转办，便于过滤无价值垃圾信息。</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="modal-actions" style={{ marginTop: '20px' }}>
              <button 
                type="button" 
                className="modal-btn submit" 
                style={{ width: '120px' }} 
                onClick={() => setShowSchemaModal(false)}
              >
                关闭手册
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
