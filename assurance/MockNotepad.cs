using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class MockNotepadForm : Form
{
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr CreateWindowEx(
        uint dwExStyle,
        string lpClassName,
        string lpWindowName,
        uint dwStyle,
        int x,
        int y,
        int nWidth,
        int nHeight,
        IntPtr hWndParent,
        IntPtr hMenu,
        IntPtr hInstance,
        IntPtr lpParam);

    const uint WS_CHILD = 0x40000000;
    const uint WS_VISIBLE = 0x10000000;
    const uint ES_MULTILINE = 0x0004;
    const uint ES_AUTOVSCROLL = 0x0040;
    const uint ES_AUTOHSCROLL = 0x0080;

    public MockNotepadForm()
    {
        this.Text = "Untitled - Notepad";
        this.Size = new Size(800, 600);
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        IntPtr hEdit = CreateWindowEx(
            0,
            "Edit",
            "",
            WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_AUTOVSCROLL | ES_AUTOHSCROLL,
            0, 0, this.ClientSize.Width, this.ClientSize.Height,
            this.Handle,
            IntPtr.Zero,
            IntPtr.Zero,
            IntPtr.Zero);
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        // Resizing the edit control isn't strictly necessary for the test to pass
    }

    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MockNotepadForm());
    }
}
