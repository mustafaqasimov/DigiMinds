// Vibration-based earthquake warning, citizen check-in and occupancy heat map vocabulary.
export const seismicMessages = {
 az: {seismicAlert:'ZƏLZƏLƏ XƏBƏRDARLIĞI',seismicSource:'Telefon sensorları eyni anda titrəmə qeydə aldı',seismicAdvice:'Çök, örtün, tutun. Titrəmə bitəndən sonra binadan çıxın və ən yaxın açıq toplaşma məntəqəsinə gedin.',
  seismicTest:'sınaq siqnalı',sensorDevices:'cihaz',sensorsOnline:'Seysmik sensorlar',sensorNeeded:'cihaz təsdiq üçün lazımdır',
  sensorLab:'Telefon sensorları (titrəşim)',sensorLabHelp:'Telefonlarda bu ünvanı açın, stolun üstünə qoyun və stolu silkələyin. Seçilmiş sayda cihaz 10 saniyə ərzində titrəmə qeydə alanda xəbərdarlıq yaranır və bağlı cihazlarda alarm çalır.',sensorReset:'Seysmik siqnalları sıfırla',sensorHttps:'Telefon sensorları yalnız HTTPS ilə işləyir: BASLAT-SENSOR.cmd ilə başladın.',
  checkinTitle:'Vəziyyətiniz necədir?',checkinHelp:'Cavabınız dispetçerə çatır. Yardım seçimləri SOS kimi göndərilir.',checkin_safe:'Təhlükəsizəm',checkin_need_help:'Yardım lazımdır',checkin_trapped:'Binada qalmışam / çıxa bilmirəm',
  checkinDone:'Cavabınız qeydə alındı',checkinChange:'Cavabı dəyiş',checkinSaved:'Status göndərildi',checkinSummary:'Vətəndaş cavabları',checkinSosNote:'SOS kimi dispetçerə göndərildi',
  heatLayer:'İstilik xəritəsi: məntəqə doluluğu',heatLegend:'Toplaşma məntəqələrinin doluluğu',heatLow:'boş',heatHigh:'dolu',heatNote:'Rəng məntəqənin hazırkı doluluğunu, yaxınlıqdakı tədbirlər varsa potensial doluluğunu göstərir.'},
 en: {seismicAlert:'EARTHQUAKE WARNING',seismicSource:'Phone sensors recorded shaking at the same time',seismicAdvice:'Drop, cover, hold on. When shaking stops, leave the building and go to the nearest open assembly point.',
  seismicTest:'test signal',sensorDevices:'devices',sensorsOnline:'Seismic sensors',sensorNeeded:'devices required to confirm',
  sensorLab:'Phone sensors (vibration)',sensorLabHelp:'Open this address on phones, lay them on a table and shake it. When the chosen number of devices record shaking within 10 seconds, a warning is raised and connected devices ring the alarm.',sensorReset:'Reset seismic signals',sensorHttps:'Phone sensors need HTTPS: start with BASLAT-SENSOR.cmd.',
  checkinTitle:'Are you OK?',checkinHelp:'Your answer reaches the dispatcher. Help options are sent as SOS.',checkin_safe:'I am safe',checkin_need_help:'I need help',checkin_trapped:'I am trapped / cannot get out',
  checkinDone:'Your answer is recorded',checkinChange:'Change answer',checkinSaved:'Status sent',checkinSummary:'Citizen responses',checkinSosNote:'sent to dispatch as SOS',
  heatLayer:'Heat map: shelter occupancy',heatLegend:'Assembly point occupancy',heatLow:'empty',heatHigh:'full',heatNote:'Colour shows current occupancy, or potential occupancy when events are nearby.'},
 ru: {seismicAlert:'ПРЕДУПРЕЖДЕНИЕ О ЗЕМЛЕТРЯСЕНИИ',seismicSource:'Датчики телефонов одновременно зафиксировали толчки',seismicAdvice:'Пригнитесь, укройтесь, держитесь. Когда толчки прекратятся, выйдите из здания и идите в ближайший открытый пункт сбора.',
  seismicTest:'тестовый сигнал',sensorDevices:'устр.',sensorsOnline:'Сейсмодатчики',sensorNeeded:'устройств нужно для подтверждения',
  sensorLab:'Датчики телефонов (вибрация)',sensorLabHelp:'Откройте этот адрес на телефонах, положите их на стол и потрясите его. Когда выбранное число устройств зафиксирует толчки за 10 секунд, появится предупреждение и на подключённых устройствах зазвучит тревога.',sensorReset:'Сбросить сейсмосигналы',sensorHttps:'Датчикам телефонов нужен HTTPS: запускайте BASLAT-SENSOR.cmd.',
  checkinTitle:'Как вы?',checkinHelp:'Ваш ответ получит диспетчер. Варианты помощи отправляются как SOS.',checkin_safe:'Я в безопасности',checkin_need_help:'Нужна помощь',checkin_trapped:'Я заблокирован / не могу выйти',
  checkinDone:'Ваш ответ записан',checkinChange:'Изменить ответ',checkinSaved:'Статус отправлен',checkinSummary:'Ответы граждан',checkinSosNote:'отправлено диспетчеру как SOS',
  heatLayer:'Тепловая карта: загрузка пунктов',heatLegend:'Загрузка пунктов сбора',heatLow:'пусто',heatHigh:'полно',heatNote:'Цвет показывает текущую загрузку или потенциальную, если рядом мероприятия.'},
};
export const CHECKIN_STATUSES = [['safe','check','green'],['need_help','medical','amber'],['trapped','collapse','danger']];
// Occupancy → colour stops shared by the heat layer and its legend.
export const HEAT_STOPS = [[0,'#2d936f'],[70,'#e0a526'],[90,'#e8742c'],[100,'#d63c2c']];
export function heatColor(percent) {
  const p = Math.max(0, Math.min(120, percent));
  let [a, b] = [HEAT_STOPS[0], HEAT_STOPS[HEAT_STOPS.length - 1]];
  for (let i = 0; i < HEAT_STOPS.length - 1; i++) if (p >= HEAT_STOPS[i][0] && p <= HEAT_STOPS[i + 1][0]) {a = HEAT_STOPS[i]; b = HEAT_STOPS[i + 1];}
  if (p >= b[0]) return b[1];
  const k = (p - a[0]) / (b[0] - a[0] || 1), hex = c => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
  const [x, y] = [hex(a[1]), hex(b[1])];
  return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * k).toString(16).padStart(2, '0')).join('');
}
