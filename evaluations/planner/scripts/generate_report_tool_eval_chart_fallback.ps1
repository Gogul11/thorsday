$output = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')) 'report\BTECH_2026\5\figures\planner_tool_selection_results.png'
$dir = Split-Path $output
New-Item -ItemType Directory -Force -Path $dir | Out-Null

Add-Type -AssemblyName System.Drawing

$source = @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;

public static class PlannerChart {
  static Font F(float size) { return new Font("Arial", size, FontStyle.Regular, GraphicsUnit.Pixel); }
  static Font F(float size, FontStyle style) { return new Font("Arial", size, style, GraphicsUnit.Pixel); }
  static void Text(Graphics g, string s, Font f, Brush b, float x, float y) { Text(g, s, f, b, x, y, StringAlignment.Near); }
  static void Text(Graphics g, string s, Font f, Brush b, float x, float y, StringAlignment align) {
    using (var sf = new StringFormat()) { sf.Alignment = align; sf.LineAlignment = StringAlignment.Near; g.DrawString(s, f, b, new PointF(x, y), sf); }
  }
  static void Line(Graphics g, Pen p, float x1, float y1, float x2, float y2) { g.DrawLine(p, x1, y1, x2, y2); }
  static void Bar(Graphics g, Brush b, float x, float y, float w, float h) { g.FillRectangle(b, x, y, w, h); }
  public static void Draw(string output) {
    const int W = 2400, H = 1050;
    using (var bmp = new Bitmap(W, H)) using (var g = Graphics.FromImage(bmp)) {
      g.SmoothingMode = SmoothingMode.AntiAlias; g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
      g.Clear(Color.White);
      using (var dark = new SolidBrush(Color.FromArgb(30, 42, 54)))
      using (var muted = new SolidBrush(Color.FromArgb(85, 96, 108)))
      using (var grid = new Pen(Color.FromArgb(224, 228, 232), 2))
      using (var border = new Pen(Color.FromArgb(205, 211, 218), 2))
      using (var blue = new SolidBrush(Color.FromArgb(53, 106, 154)))
      using (var green = new SolidBrush(Color.FromArgb(47, 125, 50)))
      using (var red = new SolidBrush(Color.FromArgb(196, 60, 57)))
      using (var grey = new SolidBrush(Color.FromArgb(138, 143, 152)))
      using (var white = new SolidBrush(Color.White)) {
        Text(g, "AgentOS planner tool-selection evaluation", F(34, FontStyle.Bold), dark, 120, 48);
        g.DrawRectangle(border, 90, 130, 820, 760); g.DrawRectangle(border, 990, 130, 1320, 760);
        Text(g, "(a) Overall outcomes", F(22, FontStyle.Bold), dark, 135, 165);
        Text(g, "(b) End-to-end exact-match accuracy", F(22, FontStyle.Bold), dark, 1035, 165);

        float lx=175, rx=835, top=245, bottom=760, max=55;
        for(int v=0; v<=50; v+=10){ float y=bottom-(v/max)*(bottom-top); Line(g,grid,lx,y,rx,y); Text(g,v.ToString(),F(17),muted,lx-22,y-10,StringAlignment.Far); }
        Line(g,border,lx,bottom,rx,bottom); Text(g,"Trials",F(18),muted,145,205);
        int[] vals={38,12,0}; string[] labels={"Correct\ntool set","Tool-call\nfailure","Incorrect\nselection"}; Brush[] fills={green,red,grey}; float[] centers={300,500,700};
        for(int i=0;i<3;i++){ float h=(vals[i]/max)*(bottom-top); Bar(g,fills[i],centers[i]-62,bottom-h,124,h); Text(g,String.Format("{0} ({1}%)",vals[i],vals[i]*2),F(19,FontStyle.Bold),dark,centers[i],bottom-h-32,StringAlignment.Center); string[] parts=labels[i].Split('\n'); Text(g,parts[0],F(17),dark,centers[i],790,StringAlignment.Center); Text(g,parts[1],F(17),dark,centers[i],814,StringAlignment.Center); }

        string[] cats={"Code Execution","Date Time","Weather","System Information","Financial Calculation","Research","Email Delivery","Document Workflow","Multi Agent"};
        double[] acc={100,83.33,83.33,83.33,83.33,80,60,60,40};
        float barX=1450, barEnd=2190, chartTop=245, row=57;
        for(int i=0;i<=100;i+=20){float x=barX+(i/100f)*(barEnd-barX); Line(g,grid,x,220,x,765); Text(g,i.ToString(),F(16),muted,x,775,StringAlignment.Center);}
        for(int i=0;i<cats.Length;i++){float y=chartTop+i*row; Text(g,cats[i],F(17),dark,1035,y+5); float w=(float)(acc[i]/100*(barEnd-barX)); Bar(g,blue,barX,y,w,30); Text(g,String.Format("{0:0.0}%",acc[i]),F(17,FontStyle.Bold),dark,barX+w+18,y+4);}
        Text(g,"Accuracy (%)",F(18),muted,1810,815,StringAlignment.Center);
        Text(g,"n = 50 trials; failures represent model tool-call failures and count as incorrect end-to-end outcomes.",F(17),muted,1200,945,StringAlignment.Center);
      }
      bmp.Save(output, System.Drawing.Imaging.ImageFormat.Png);
    }
  }
}
'@
Add-Type -TypeDefinition $source -ReferencedAssemblies 'System.Drawing'
[PlannerChart]::Draw($output)
Write-Output "Wrote $output"
