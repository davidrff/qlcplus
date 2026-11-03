using System.Globalization;
using System.Text;
using NAudio.CoreAudioApi;
using NAudio.Wave;
namespace SafetyMonitor;
internal sealed partial class MainForm : Form
{
    readonly ComboBox deviceBox=new(){DropDownStyle=ComboBoxStyle.DropDownList,Width=420};
    readonly NumericUpDown leftCh=Num(0,31,0),rightCh=Num(0,31,1),micCh=Num(-1,31,-1);
    readonly NumericUpDown warnPeak=Num(-60,0,-3,1),critPeak=Num(-60,0,-1,1),warnSpl=Num(40,140,95,1),critSpl=Num(40,140,100,1),calRef=Num(60,130,94,1);
    readonly Label lPeakL=Big(),lPeakR=Big(),lRmsL=Med(),lRmsR=Med(),lHoldL=Med(),lHoldR=Med(),lCrestL=Med(),lCrestR=Med(),lSpl=Big(),lLeq=Med(),lBands=Med(),lStatus=Big();
    readonly Label lInfo=new(){AutoSize=true,ForeColor=Color.Silver};
    readonly Button startBtn=new(){Text="START",Width=100},stopBtn=new(){Text="STOP",Width=100,Enabled=false},calibrateBtn=new(){Text="CALIBRA SPL",Width=120},eventBtn=new(){Text="START EVENTO",Width=120};
    readonly CheckBox soundBox=new(){Text="Suono allarme",AutoSize=true};
    readonly ListBox log=new(){Dock=DockStyle.Fill}; readonly System.Windows.Forms.Timer uiTimer=new(){Interval=100}; readonly object gate=new();
    readonly MMDeviceEnumerator enumerator=new(); readonly List<MMDevice> devices=[]; WasapiCapture? capture; WaveFormat? format;
    double peakL=-120,peakR=-120,rmsL=-120,rmsR=-120,holdL=-120,holdR=-120,low=-120,mid=-120,high=-120,micDbfs=double.NaN;
    long clipsL,clipsR; double splOffset=double.NaN,splNow=double.NaN,leqEnergy,leqSeconds; DateTime holdTimeL,holdTimeR; bool eventActive; DateTime eventStart; readonly List<string> eventRows=[]; string? lastAlarm;
    public MainForm(){Text="Safety Monitor";Width=1180;Height=760;BackColor=Color.FromArgb(13,17,23);ForeColor=Color.White;Font=new Font("Segoe UI",10);
        var top=new FlowLayoutPanel{Dock=DockStyle.Top,Height=92,Padding=new Padding(8),BackColor=Color.FromArgb(22,27,34)};top.Controls.AddRange([Lbl("Input"),deviceBox,Lbl("L"),leftCh,Lbl("R"),rightCh,Lbl("MIC"),micCh,startBtn,stopBtn,eventBtn,soundBox]);
        var cfg=new FlowLayoutPanel{Dock=DockStyle.Top,Height=54,Padding=new Padding(8),BackColor=Color.FromArgb(33,38,45)};cfg.Controls.AddRange([Lbl("Peak warn"),warnPeak,Lbl("crit"),critPeak,Lbl("SPL warn"),warnSpl,Lbl("crit"),critSpl,Lbl("Rif calibrazione"),calRef,calibrateBtn]);
        var meters=new TableLayoutPanel{Dock=DockStyle.Top,Height=330,ColumnCount=4,RowCount=4,Padding=new Padding(12)};for(int i=0;i<4;i++)meters.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,25));
        AddCell(meters,"PEAK L dBFS",lPeakL,0,0);AddCell(meters,"PEAK R dBFS",lPeakR,1,0);AddCell(meters,"SPL",lSpl,2,0);AddCell(meters,"STATUS",lStatus,3,0);AddCell(meters,"RMS L",lRmsL,0,1);AddCell(meters,"RMS R",lRmsR,1,1);AddCell(meters,"LEQ",lLeq,2,1);AddCell(meters,"BANDS",lBands,3,1);AddCell(meters,"PEAK HOLD L",lHoldL,0,2);AddCell(meters,"PEAK HOLD R",lHoldR,1,2);AddCell(meters,"CREST L",lCrestL,0,3);AddCell(meters,"CREST R",lCrestR,1,3);
        var infoPanel=new Panel{Dock=DockStyle.Top,Height=34,Padding=new Padding(10,6,0,0)};infoPanel.Controls.Add(lInfo);Controls.Add(log);Controls.Add(infoPanel);Controls.Add(meters);Controls.Add(cfg);Controls.Add(top);
        startBtn.Click+=(_,_)=>StartCapture();stopBtn.Click+=(_,_)=>StopCapture();calibrateBtn.Click+=(_,_)=>Calibrate();eventBtn.Click+=(_,_)=>ToggleEvent();uiTimer.Tick+=(_,_)=>RefreshUi();FormClosed+=(_,_)=>{StopCapture();foreach(var d in devices)d.Dispose();enumerator.Dispose();};LoadDevices();uiTimer.Start();SetStatus("IDLE",Color.Silver);}
    static NumericUpDown Num(decimal min,decimal max,decimal value,int decimals=0)=>new(){Minimum=min,Maximum=max,Value=value,DecimalPlaces=decimals,Width=70,Increment=decimals>0?0.1m:1m};
    static Label Lbl(string s)=>new(){Text=s,AutoSize=true,Margin=new Padding(8,8,2,0),ForeColor=Color.Gainsboro}; static Label Big()=>new(){Text="--",AutoSize=true,Font=new Font("Segoe UI Semibold",25),ForeColor=Color.White}; static Label Med()=>new(){Text="--",AutoSize=true,Font=new Font("Segoe UI Semibold",15),ForeColor=Color.White};
    static void AddCell(TableLayoutPanel t,string title,Control value,int c,int r){var p=new Panel{Dock=DockStyle.Fill,Margin=new Padding(6),BackColor=Color.FromArgb(22,27,34)};p.Controls.Add(value);value.Location=new Point(12,34);p.Controls.Add(new Label{Text=title,AutoSize=true,ForeColor=Color.DarkGray,Location=new Point(12,10)});t.Controls.Add(p,c,r);}
    void LoadDevices(){deviceBox.Items.Clear();devices.Clear();foreach(var d in enumerator.EnumerateAudioEndPoints(DataFlow.Capture,DeviceState.Active)){devices.Add(d);deviceBox.Items.Add(d.FriendlyName);}if(deviceBox.Items.Count>0)deviceBox.SelectedIndex=0;}
}
