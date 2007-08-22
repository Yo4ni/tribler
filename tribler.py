#!/usr/bin/python

#########################################################################
#
# Author : Choopan RATTANAPOKA, Jie Yang, Arno Bakker
#
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#########################################################################

# Arno: G*dd*mn M2Crypto overrides the method for https:// in the
# standard Python libraries. This causes msnlib to fail and makes Tribler
# freakout when "http://www.tribler.org/version" is redirected to
# "https://www.tribler.org/version/" (which happened during our website
# changeover) Until M2Crypto 0.16 is patched I'll restore the method to the
# original, as follows.
#
# This must be done in the first python file that is started.
#

import urllib
original_open_https = urllib.URLopener.open_https
import M2Crypto
urllib.URLopener.open_https = original_open_https

import sys, locale
import os
import wx, commands
from wx import xrc
#import hotshot

if sys.platform == "darwin":
    # on Mac, we can only load VLC libraries
    # relative to the location of tribler.py
    os.chdir(os.path.abspath(os.path.dirname(sys.argv[0])))

from threading import Thread, Timer, Event,currentThread,enumerate
from time import time, ctime, sleep
from traceback import print_exc, print_stack
from cStringIO import StringIO
import urllib

from interconn import ServerListener, ClientPassParam
from launchmanycore import ABCLaunchMany

from ABC.Toolbars.toolbars import ABCBottomBar2, ABCStatusBar, ABCMenuBar, ABCToolBar
from ABC.GUI.menu import ABCMenu
from ABC.Scheduler.scheduler import ABCScheduler

from webservice import WebListener

if (sys.platform == 'win32'):
    from Dialogs.regdialog import RegCheckDialog

from ABC.GUI.list import ManagedList
from Utility.utility import Utility
from Utility.constants import * #IGNORE:W0611

from Tribler.__init__ import tribler_init, tribler_done
from BitTornado.__init__ import product_name
from safeguiupdate import DelayedInvocation,FlaglessDelayedInvocation
import webbrowser
from Tribler.Dialogs.MugshotManager import MugshotManager
from Tribler.vwxGUI.GuiUtility import GUIUtility
import Tribler.vwxGUI.updateXRC as updateXRC
from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL
from Tribler.Video.VideoServer import VideoHTTPServer
from Tribler.Dialogs.GUIServer import GUIServer
from Tribler.vwxGUI.TasteHeart import set_tasteheart_bitmaps
from Tribler.vwxGUI.perfBar import set_perfBar_bitmaps
from Tribler.Dialogs.BandwidthSelector import BandwidthSelector
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Dialogs.activities import *
from Tribler.DecentralizedTracking import mainlineDHT
from Tribler.DecentralizedTracking.rsconvert import RawServerConverter
from Tribler.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker

from Tribler.notification import init as notification_init
from Tribler.vwxGUI.font import *
from Tribler.Web2.util.update import Web2Updater

from Tribler.CacheDB.CacheDBHandler import BarterCastDBHandler
from Tribler.Overlay.permid import permid_for_user
from BitTornado.download_bt1 import EVIL

DEBUG = True
ALLOW_MULTIPLE = False
start_time = 0
start_time2 = 0


################################################################
#
# Class: FileDropTarget
#
# To enable drag and drop for ABC list in main menu
#
################################################################
class FileDropTarget(wx.FileDropTarget): 
    def __init__(self, utility):
        # Initialize the wsFileDropTarget Object 
        wx.FileDropTarget.__init__(self) 
        # Store the Object Reference for dropped files 
        self.utility = utility
      
    def OnDropFiles(self, x, y, filenames):
        for filename in filenames:
            self.utility.queue.addtorrents.AddTorrentFromFile(filename)
        return True


##############################################################
#
# Class : ABCList
#
# ABC List class that contains the torrent list
#
############################################################## 
class ABCList(ManagedList):
    def __init__(self, parent):
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        
        prefix = 'column'
        minid = 4
        maxid = 26
        exclude = []
        rightalign = [COL_PROGRESS, 
                      COL_SIZE, 
                      COL_DLSPEED, 
                      COL_ULSPEED, 
                      COL_RATIO, 
                      COL_PEERPROGRESS, 
                      COL_DLSIZE, 
                      COL_ULSIZE, 
                      COL_TOTALSPEED]

        ManagedList.__init__(self, parent, style, prefix, minid, maxid, exclude, rightalign)
        
        dragdroplist = FileDropTarget(self.utility)
        self.SetDropTarget(dragdroplist)
        
        self.lastcolumnsorted = -1
        self.reversesort = 0

        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColLeftClick)

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnItemSelected)
        
        # Bring up advanced details on left double click
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        
        # Bring up local settings on middle double click
        self.Bind(wx.EVT_MIDDLE_DCLICK, self.utility.actions[ACTION_LOCALUPLOAD].action)

    # Do thing when keys are pressed down
    def OnKeyDown(self, event):
        keycode = event.GetKeyCode()
        if event.CmdDown():
            if keycode == ord('a') or keycode == ord('A'):
                # Select all files (CTRL-A)
                self.selectAll()
            elif keycode == ord('x') or keycode == ord('X'):
                # Invert file selection (CTRL-X)
                self.invertSelection()
        elif keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
            # Open advanced details (Enter)
            self.utility.actions[ACTION_DETAILS].action()
        elif keycode == wx.WXK_SPACE:
            # Open local settings (Space)
            self.utility.actions[ACTION_LOCALUPLOAD].action()
        elif keycode == 399:
            # Open right-click menu (windows menu key)
            self.OnItemSelected()
        
        event.Skip()
        
    def OnColLeftClick(self, event):
        rank = event.GetColumn()
        colid = self.columns.getIDfromRank(rank)
        if colid == self.lastcolumnsorted:
            self.reversesort = 1 - self.reversesort
        else:
            self.reversesort = 0
        self.lastcolumnsorted = colid
        self.utility.queue.sortList(colid, self.reversesort)       
        
    def selectAll(self):
        self.updateSelected(select = range(0, self.GetItemCount()))

    def updateSelected(self, unselect = None, select = None):
        if unselect is not None:
            for index in unselect:
                self.SetItemState(index, 0, wx.LIST_STATE_SELECTED)
        if select is not None:
            for index in select:
                self.Select(index)
        self.SetFocus()

    def getTorrentSelected(self, firstitemonly = False, reverse = False):
        queue = self.utility.queue
        
        torrentselected = []
        for index in self.getSelected(firstitemonly, reverse):
            ABCTorrentTemp = queue.getABCTorrent(index = index)
            if ABCTorrentTemp is not None:
                torrentselected.append(ABCTorrentTemp)
        return torrentselected

    def OnItemSelected(self, event = None):
        selected = self.getTorrentSelected()
        if not selected:
            return

        popupmenu = ABCMenu(self.utility, 'menu_listrightclick')

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        if event is None:
            # use the position of the first selected item (key event)
            ABCTorrentTemp = selected[0]
            position = self.GetItemPosition(ABCTorrentTemp.listindex)
        else:
            # use the cursor position (mouse event)
            position = event.GetPosition()
        
        self.PopupMenu(popupmenu, position)

    def OnLeftDClick(self, event):
        event.Skip()
        try:
            self.utility.actions[ACTION_DETAILS].action()
        except:
            print_exc()


##############################################################
#
# Class : ABCPanel
#
# Main ABC Panel class
#
############################################################## 
class ABCPanel(wx.Panel):
    def __init__(self, parent):
        style = wx.CLIP_CHILDREN
        wx.Panel.__init__(self, parent, -1, style = style)

        #Debug Output.
        sys.stdout.write('Preparing GUI.\n');
        
        self.utility    = parent.utility
        self.utility.window = self
        self.queue = self.utility.queue
               
        # List of deleting torrents events that occur when the RateManager is active
        # Such events are processed after the RateManager finishes
        # postponedevents is a list of tupples : each tupple contains the method of ABCPanel to be called to
        # deal with the event and the event.
        self.postponedevents = []

        #Manual Bittorrent Adding UI
        ##############################
        colSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.list = ABCList(self)
        self.utility.list = self.list
        colSizer.Add(self.list, 1, wx.ALL|wx.EXPAND, 3)
            
        """
        # Add status bar
        statbarbox = wx.BoxSizer(wx.HORIZONTAL)
        self.sb_buttons = ABCStatusButtons(self,self.utility)
        statbarbox.Add(self.sb_buttons, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        self.abc_sb = ABCStatusBar(self,self.utility)
        statbarbox.Add(self.abc_sb, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        colSizer.Add(statbarbox, 0, wx.ALL|wx.EXPAND, 0)
        """
        
        #colSizer.Add(self.contentPanel, 1, wx.ALL|wx.EXPAND, 3)
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        
        self.list.SetFocus()
        
        
    def getSelectedList(self, event = None):
        return self.list

    ######################################
    # Update ABC on-the-fly
    ######################################
    def updateColumns(self, force = False):
        # Update display in column for inactive torrent
        for ABCTorrentTemp in self.utility.torrents["all"]:
            ABCTorrentTemp.updateColumns(force = force)
 
      
##############################################################
#
# Class : ABCTaskBarIcon
#
# Task Bar Icon
#
############################################################## 
class ABCTaskBarIcon(wx.TaskBarIcon):
    def __init__(self, parent):
        wx.TaskBarIcon.__init__(self)
        
        self.utility = parent.utility
        
        self.TBMENU_RESTORE = wx.NewId()

        # setup a taskbar icon, and catch some events from it
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, parent.onTaskBarActivate)
        self.Bind(wx.EVT_MENU, parent.onTaskBarActivate, id = self.TBMENU_RESTORE)
               
        self.updateIcon(False)
        
    def updateIcon(self,iconifying = False):
        remove = True
        
        mintray = self.utility.config.Read('mintray', "int")
        if (mintray >= 2) or ((mintray >= 1) and iconifying):
            remove = False
        
        if remove and self.IsIconInstalled():
            self.RemoveIcon()
        elif not remove and not self.IsIconInstalled():
            self.SetIcon(self.utility.icon, product_name)
        
    def CreatePopupMenu(self):        
        menu = wx.Menu()
        
        self.utility.actions[ACTION_STOPALL].addToMenu(menu, bindto = self)
        self.utility.actions[ACTION_UNSTOPALL].addToMenu(menu, bindto = self)
        menu.AppendSeparator()
        menu.Append(self.TBMENU_RESTORE, self.utility.lang.get('showabcwindow'))
        self.utility.actions[ACTION_EXIT].addToMenu(menu, bindto = self)
        return menu


##############################################################
#
# Class : ABColdFrame
#
# Main ABC Frame class that contains menu and menu bar management
# and contains ABCPanel
#
############################################################## 
class ABCOldFrame(wx.Frame,FlaglessDelayedInvocation):
    def __init__(self, ID, params, utility):
        self.utility = utility
        #self.utility.frame = self
        
        title = "Old Interface"
        # Get window size and position from config file
        size = (400,400)
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        
        wx.Frame.__init__(self, None, ID, title, size = size, style = style)
        
        FlaglessDelayedInvocation.__init__(self)

        self.GUIupdate = True

        self.window = ABCPanel(self)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        self.tb = ABCToolBar(self) # new Tribler gui has no toolbar
        self.SetToolBar(self.tb)

            
    def onFocus(self, event = None):
        if event is not None:
            event.Skip()
        self.window.getSelectedList(event).SetFocus()

    def OnCloseWindow(self, event = None):
        self.Hide()

# Custom class loaded by XRC
class ABCFrame(wx.Frame, DelayedInvocation):
    def __init__(self, *args):
        if len(args) == 0:
            pre = wx.PreFrame()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Frame.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.params = self.guiUtility.params
        self.utility.frame = self
        
        title = self.utility.lang.get('title') + \
                " " + \
                self.utility.lang.get('version')
        
        # Get window size and position from config file
        size, position = self.getWindowSettings()
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        
        self.SetSize(size)
        self.SetPosition(position)
        self.SetTitle(title)
        tt = self.GetToolTip()
        if tt is not None:
            tt.SetTip('')
        
        #wx.Frame.__init__(self, None, ID, title, position, size, style = style)
        
        self.doneflag = Event()
        DelayedInvocation.__init__(self)

        dragdroplist = FileDropTarget(self.utility)
        self.SetDropTarget(dragdroplist)

        self.tbicon = None

        # Arno: see ABCPanel
        #self.abc_sb = ABCStatusBar(self,self.utility)
        #self.SetStatusBar(self.abc_sb)

        """
        # Add status bar
        statbarbox = wx.BoxSizer(wx.HORIZONTAL)
        self.sb_buttons = ABCStatusButtons(self,self.utility)
        statbarbox.Add(self.sb_buttons, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        self.abc_sb = ABCStatusBar(self,self.utility)
        statbarbox.Add(self.abc_sb, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 0)
        #colSizer.Add(statbarbox, 0, wx.ALL|wx.EXPAND, 0)
        self.SetStatusBar(statbarbox)
        """
        
        
        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        # Don't update GUI as often when iconized
        self.GUIupdate = True

        # Start the scheduler before creating the ListCtrl
        self.utility.queue  = ABCScheduler(self.utility)
        #self.window = ABCPanel(self)
        #self.abc_sb = self.window.abc_sb
        
        
        self.oldframe = ABCOldFrame(-1, self.params, self.utility)
        self.oldframe.Refresh()
        self.oldframe.Layout()
        #self.oldframe.Show(True)
        
        self.window = self.GetChildren()[0]
        self.window.utility = self.utility
        
        """
        self.list = ABCList(self.window)
        self.list.Show(False)
        self.utility.list = self.list
        print self.window.GetName()
        self.window.list = self.list
        self.utility.window = self.window
        """
        #self.window.sb_buttons = ABCStatusButtons(self,self.utility)
        
        self.utility.window.postponedevents = []
        
        # Menu Options
        ############################
        menuBar = ABCMenuBar(self)
        if sys.platform == "darwin":
            wx.App.SetMacExitMenuItemId(wx.ID_CLOSE)
        self.SetMenuBar(menuBar)
        
        #self.tb = ABCToolBar(self) # new Tribler gui has no toolbar
        #self.SetToolBar(self.tb)
        
        self.buddyFrame = None
        self.fileFrame = None
        self.buddyFrame_page = 0
        self.buddyFrame_size = (800, 500)
        self.buddyFrame_pos = None
        self.fileFrame_size = (800, 500)
        self.fileFrame_pos = None
        
        # Menu Events 
        ############################

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
#        self.Bind(wx.EVT_MENU, self.OnMenuExit, id = wx.ID_CLOSE)

        # leaving here for the time being:
        # wxMSW apparently sends the event to the App object rather than
        # the top-level Frame, but there seemed to be some possibility of
        # change
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.OnCloseWindow)
        
        try:
            self.tbicon = ABCTaskBarIcon(self)
        except:
            pass
        self.Bind(wx.EVT_ICONIZE, self.onIconify)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_MAXIMIZE, self.onSize)
        #self.Bind(wx.EVT_IDLE, self.onIdle)
        
        # Start up the controller
        self.utility.controller = ABCLaunchMany(self.utility)
        self.utility.controller.start()
        
        # Start up mainline DHT
        rsconvert = RawServerConverter(self.utility.controller.get_rawserver())
        mainlineDHT.init('', self.utility.listen_port, self.utility.getConfigPath(),rawserver=rsconvert)
        # Create torrent-liveliness checker based on DHT
        c = mainlineDHTChecker.getInstance()
        c.register(mainlineDHT.dht)

        # Give GUI time to set up stuff
        wx.Yield()

        #if server start with params run it
        #####################################
        
        if DEBUG:
            print >>sys.stderr,"abc: wxFrame: params is",self.params
        
        if self.params[0] != "":
            success, msg, ABCTorrentTemp = self.utility.queue.addtorrents.AddTorrentFromFile(self.params[0],caller=CALLER_ARGV)

        self.utility.queue.postInitTasks(self.params)

        if self.params[0] != "":
            # Update torrent.list, but after having read the old list of torrents, otherwise we get interference
            ABCTorrentTemp.torrentconfig.writeSrc(False)
            self.utility.torrentconfig.Flush()

        self.videoFrame = None
        feasible = return_feasible_playback_modes(self.utility.getPath())
        if PLAYBACKMODE_INTERNAL in feasible:
            # This means vlc is available
            from Tribler.Video.EmbeddedPlayer import VideoFrame
            self.videoFrame = VideoFrame(self)

            #self.videores = xrc.XmlResource("Tribler/vwxGUI/MyPlayer.xrc")
            #self.videoframe = self.videores.LoadFrame(None, "MyPlayer")
            #self.videoframe.Show()
            
            videoplayer = VideoPlayer.getInstance()
            videoplayer.set_parentwindow(self.videoFrame)
        else:
            videoplayer = VideoPlayer.getInstance()
            videoplayer.set_parentwindow(self)

        sys.stdout.write('GUI Complete.\n')

        self.Show(True)
        
        
        # Just for debugging: add test permids and display top 5 peers from which the most is downloaded in bartercastdb
        bartercastdb = BarterCastDBHandler()
        mypermid = bartercastdb.my_permid
        
        if DEBUG:
            bartercastdb.incrementItem((mypermid, "testpermid_1"), 'uploaded', 1024)
            bartercastdb.incrementItem((mypermid, "testpermid_1"), 'downloaded', 20000)
                    
            bartercastdb.incrementItem((mypermid, "testpermid_2"), 'uploaded', 40000)
            bartercastdb.incrementItem((mypermid, "testpermid_2"), 'downloaded', 60000)
            
            top = bartercastdb.getTopNPeers(5)
    
            print 'My Permid: ', permid_for_user(mypermid)
            
            print 'Top 5 BarterCast peers:'
            print '======================='
    
            i = 1
            for (permid, up, down) in top:
                print '%2d: %15s  -  %10d up  %10d down' % (i, bartercastdb.getName(permid), up, down)
                i += 1
        
        
        # Check to see if ABC is associated with torrents
        #######################################################
        if (sys.platform == 'win32'):
            if self.utility.config.Read('associate', "boolean"):
                if self.utility.regchecker and not self.utility.regchecker.testRegistry():
                    dialog = RegCheckDialog(self)
                    dialog.ShowModal()
                    dialog.Destroy()

        self.checkVersion()

        
    def checkVersion(self):
        t = Timer(2.0, self._checkVersion)
        t.start()
        
    def _checkVersion(self):
        my_version = self.utility.getVersion()
        try:
            curr_status = urllib.urlopen('http://tribler.org/version').readlines()
            line1 = curr_status[0]
            if len(curr_status) > 1:
                self.update_url = curr_status[1].strip()
            else:
                self.update_url = 'http://tribler.org'
            _curr_status = line1.split()
            self.curr_version = _curr_status[0]
            if self.newversion(self.curr_version, my_version):
                # Arno: we are a separate thread, delegate GUI updates to MainThread
                self.upgradeCallback()
            
            # Also check new version of web2definitions for youtube etc. search
            Web2Updater(self.utility).checkUpdate()
        except Exception,e:
            print >> sys.stderr, "Tribler: Version check failed", ctime(time()), str(e)
            #print_exc()
            
    def newversion(self, curr_version, my_version):
        curr = curr_version.split('.')
        my = my_version.split('.')
        if len(my) >= len(curr):
            nversion = len(my)
        else:
            nversion = len(curr)
        for i in range(nversion):
            if i < len(my):
                my_v = int(my[i])
            else:
                my_v = 0
            if i < len(curr):
                curr_v = int(curr[i])
            else:
                curr_v = 0
            if curr_v > my_v:
                return True
            elif curr_v < my_v:
                return False
        return False

    def upgradeCallback(self):
        self.invokeLater(self.OnUpgrade)    
        # TODO: warn multiple times?
    
    def OnUpgrade(self, event=None):
        self.setActivity(ACT_NEW_VERSION)
            
    def onFocus(self, event = None):
        if event is not None:
            event.Skip()
        #self.window.getSelectedList(event).SetFocus()
        
    def setGUIupdate(self, update):
        oldval = self.GUIupdate
        self.GUIupdate = update
        
        if self.GUIupdate and not oldval:
            # Force an update of all torrents
            for torrent in self.utility.torrents["all"]:
                torrent.updateColumns()
                torrent.updateColor()


    def taskbarCallback(self):
        self.invokeLater(self.onTaskBarActivate,[])


    #######################################
    # minimize to tray bar control
    #######################################
    def onTaskBarActivate(self, event = None):
        self.Iconize(False)
        self.Show(True)
        self.Raise()
        
        if self.tbicon is not None:
            self.tbicon.updateIcon(False)

        #self.window.list.SetFocus()

        # Resume updating GUI
        self.setGUIupdate(True)

    def onIconify(self, event = None):
        # This event handler is called both when being minimalized
        # and when being restored.
        if DEBUG:
            if event is not None:
                print  >> sys.stderr,"abc: onIconify(",event.Iconized()
            else:
                print  >> sys.stderr,"abc: onIconify event None"
        if event.Iconized():                                                                                                               
            if (self.utility.config.Read('mintray', "int") > 0
                and self.tbicon is not None):
                self.tbicon.updateIcon(True)
                self.Show(False)

            # Don't update GUI while minimized
            self.setGUIupdate(False)
        else:
            self.setGUIupdate(True)
        if event is not None:
            event.Skip()

    def onSize(self, event = None):
        # Arno: On Windows when I enable the tray icon and then change
        # virtual desktop (see MS DeskmanPowerToySetup.exe)
        # I get a onIconify(event.Iconized()==True) event, but when
        # I switch back, I don't get an event. As a result the GUIupdate
        # remains turned off. The wxWidgets wiki on the TaskBarIcon suggests
        # catching the onSize event. 
        
        if DEBUG:
            if event is not None:
                print  >> sys.stderr,"abc: onSize:",self.GetSize()
            else:
                print  >> sys.stderr,"abc: onSize: None"
        self.setGUIupdate(True)
        if event is not None:
            if event.GetEventType() == wx.EVT_MAXIMIZE:
                self.window.SetClientSize(self.GetClientSize())
            event.Skip()
        

        # Refresh subscreens
        self.refreshNeeded = True
        self.guiUtility.refreshOnResize()
        
    def onIdle(self, event = None):
        """
        Only refresh screens (especially detailsPanel) when resizes are finished
        This gives less flickering, but doesnt look pretty, so i commented it out
        """
        if self.refreshNeeded:
            self.guiUtility.refreshOnResize()
            self.refreshNeeded = False
        
    def getWindowSettings(self):
        width = self.utility.config.Read("window_width")
        height = self.utility.config.Read("window_height")
        try:
            size = wx.Size(int(width), int(height))
        except:
            size = wx.Size(710, 400)
        
        x = self.utility.config.Read("window_x")
        y = self.utility.config.Read("window_y")
        if (x == "" or y == ""):
            position = wx.DefaultPosition
        else:
            position = wx.Point(int(x), int(y))
            
        return size, position     
        
    def saveWindowSettings(self):
        width, height = self.GetSizeTuple()
        x, y = self.GetPositionTuple()
        self.utility.config.Write("window_width", width)
        self.utility.config.Write("window_height", height)
        self.utility.config.Write("window_x", x)
        self.utility.config.Write("window_y", y)

        self.utility.config.Flush()
       
    ##################################
    # Close Program
    ##################################
               
    def OnCloseWindow(self, event = None):
        if event != None:
            nr = event.GetEventType()
            lookup = { wx.EVT_CLOSE.evtType[0]: "EVT_CLOSE", wx.EVT_QUERY_END_SESSION.evtType[0]: "EVT_QUERY_END_SESSION", wx.EVT_END_SESSION.evtType[0]: "EVT_END_SESSION" }
            if nr in lookup: nr = lookup[nr]
            print "Closing due to event ",nr
            print >>sys.stderr,"Closing due to event ",nr
        else:
            print "Closing untriggered by event"
        
        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            return

        # Check to see if we can veto the shutdown
        # (might not be able to in case of shutting down windows)
        if event is not None:
            try:
                if event.CanVeto() and self.utility.config.Read('confirmonclose', "boolean") and not event.GetEventType() == wx.EVT_QUERY_END_SESSION.evtType[0]:
                    dialog = wx.MessageDialog(None, self.utility.lang.get('confirmmsg'), self.utility.lang.get('confirm'), wx.OK|wx.CANCEL)
                    result = dialog.ShowModal()
                    dialog.Destroy()
                    if result != wx.ID_OK:
                        event.Veto()
                        return
            except:
                data = StringIO()
                print_exc(file = data)
                sys.stderr.write(data.getvalue())
                pass
            
        self.utility.abcquitting = True
        self.GUIupdate = False
        
        self.guiUtility.guiOpen.clear()
        
        # Close the Torrent Maker
        self.utility.actions[ACTION_MAKETORRENT].closeWin()

        try:
            self.utility.webserver.stop()
        except:
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
            pass

        try:
            # tell scheduler to close all active thread
            self.utility.queue.clearScheduler()
        except:
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
            pass

        try:
            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
            #print_exc(file=sys.stderr)
            print_exc()

        try:
            if self.buddyFrame is not None:
                self.buddyFrame.Destroy()
            if self.fileFrame is not None:
                self.fileFrame.Destroy()
            if self.videoFrame is not None:
                self.videoFrame.Destroy()
        except:
            pass

        self.oldframe.Destroy()

        try:
            if self.tbicon is not None:
                self.tbicon.RemoveIcon()
                self.tbicon.Destroy()
            self.Destroy()
        except:
            data = StringIO()
            print_exc(file = data)
            sys.stderr.write(data.getvalue())
            pass

        # Arno: at the moment, Tribler gets a segmentation fault when the
        # tray icon is always enabled. This SEGV occurs in the wx mainloop
        # which is entered as soon as we leave this method. Hence I placed
        # tribler_done() here, so the database are closed properly
        # before the crash.
        #
        # Arno, 2007-02-28: Preferably this should be moved to the main 
        # run() method below, that waits a while to allow threads to finish.
        # Ideally, the database should still be open while they finish up.
        # Because of the crash problem with the icontray this is the safer
        # place.
        #
        # Arno, 2007-08-10: When a torrentfile is passed on the command line,
        # the client will crash just after this point due to unknown reasons
        # (it even does it when we don't look at the cmd line args at all!)
        # Hence, for safety, I close the DB here already. 
        #if sys.platform == 'linux2':
        #
        
        #tribler_done(self.utility.getConfigPath())            
        
        if DEBUG:    
            print >>sys.stderr,"abc: OnCloseWindow END"

        if DEBUG:
            ts = enumerate()
            for t in ts:
                print >>sys.stderr,"abc: Thread still running",t.getName(),"daemon",t.isDaemon()



    def onWarning(self,exc):
        msg = self.utility.lang.get('tribler_startup_nonfatalerror')
        msg += str(exc.__class__)+':'+str(exc)
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def onUPnPError(self,upnp_type,listenport,error_type,exc=None,listenproto='TCP'):

        if error_type == 0:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error1')
        elif error_type == 1:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error2')+unicode(str(exc))+self.utility.lang.get('tribler_upnp_error2_postfix')
        elif error_type == 2:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' ')+self.utility.lang.get('tribler_upnp_error3')
        else:
            errormsg = unicode(' UPnP mode '+str(upnp_type)+' Unknown error')

        msg = self.utility.lang.get('tribler_upnp_error_intro')
        msg += listenproto+' '
        msg += str(listenport)
        msg += self.utility.lang.get('tribler_upnp_error_intro_postfix')
        msg += errormsg
        msg += self.utility.lang.get('tribler_upnp_error_extro') 

        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('tribler_warning'), wx.OK|wx.ICON_WARNING)
        result = dlg.ShowModal()
        dlg.Destroy()

    def onReachable(self,event=None):
        """ Called by GUI thread """
        if self.firewallStatus is not None:
            self.firewallStatus.setToggled(True)
            tt = self.firewallStatus.GetToolTip()
            if tt is not None:
                tt.SetTip(self.utility.lang.get('reachable_tooltip'))


    def setActivity(self,type,msg=u''):
    
        if currentThread().getName() != "MainThread":
            print  >> sys.stderr,"abc: setActivity thread",currentThread().getName(),"is NOT MAIN THREAD"
            print_stack()
    
        if type == ACT_NONE:
            prefix = u''
            msg = u''
        elif type == ACT_UPNP:
            prefix = self.utility.lang.get('act_upnp')
        elif type == ACT_REACHABLE:
            prefix = self.utility.lang.get('act_reachable')
        elif type == ACT_GET_EXT_IP_FROM_PEERS:
            prefix = self.utility.lang.get('act_get_ext_ip_from_peers')
        elif type == ACT_MEET:
            prefix = self.utility.lang.get('act_meet')
        elif type == ACT_GOT_METADATA:
            prefix = self.utility.lang.get('act_got_metadata')
        elif type == ACT_RECOMMEND:
            prefix = self.utility.lang.get('act_recommend')
        elif type == ACT_DISK_FULL:
            prefix = self.utility.lang.get('act_disk_full')   
        elif type == ACT_NEW_VERSION:
            prefix = self.utility.lang.get('act_new_version')   
        if msg == u'':
            text = prefix
        else:
            text = unicode( prefix+u' '+msg)
            
        if DEBUG:
            print  >> sys.stderr,"abc: Setting activity",`text`,"EOT"
        self.messageField.SetLabel(text)


class TorThread(Thread):
    
    def __init__(self):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("TorThread"+self.getName())
        self.child_out = None
        self.child_in = None
        
    def run(self):
        if EVIL:
            ## TOR EVIL
            
            if DEBUG:
                print >>sys.stderr,"TorThread starting",currentThread().getName()
            if sys.platform == "win32":
                # Not "Nul:" but "nul" is /dev/null on Win32
                sink = 'nul'
            else:
                sink = '/dev/null'
    
            (self.child_out,self.child_in) = os.popen2( "tor.exe  --log err-err > %s 2>&1" % (sink), 'b' )
            #(child_out,child_in) = os.popen2( "tor.exe --log err-err", 'b' )
            while True:
                msg = child_in.read()
                if DEBUG:
                    print >>sys.stderr,"TorThread: tor said",msg
                sleep(1)

    def shutdown(self):
        if self.child_out is not None:
            self.child_out.close()
        if self.child_in is not None:
            self.child_in.close()
            

##############################################################
#
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
##############################################################
class ABCApp(wx.App,FlaglessDelayedInvocation):
    def __init__(self, x, params, single_instance_checker, abcpath):
        global start_time, start_time2
        start_time2 = time()
        #print "[StartUpDebug]----------- from ABCApp.__init__ ----------Tribler starts up at", ctime(start_time2), "after", start_time2 - start_time
        self.params = params
        self.single_instance_checker = single_instance_checker
        self.abcpath = abcpath
        self.error = None
        wx.App.__init__(self, x)
        
    def OnInit(self):
        try:
            self.utility = Utility(self.abcpath)
            # Set locale to determine localisation
            locale.setlocale(locale.LC_ALL, '')

            sys.stdout.write('Client Starting Up.\n')
            sys.stdout.write('Build: ' + self.utility.lang.get('build') + '\n')
            
            bm = wx.Bitmap(os.path.join(self.utility.getPath(),'icons','splash.jpg'),wx.BITMAP_TYPE_JPEG)
            #s = wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.RESIZE_BORDER | wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.CLIP_CHILDREN
            #s = wx.SIMPLE_BORDER|wx.FRAME_NO_TASKBAR|wx.FRAME_FLOAT_ON_PARENT
            self.splash = wx.SplashScreen(bm, wx.SPLASH_CENTRE_ON_SCREEN|wx.SPLASH_TIMEOUT, 1000, None, -1)
            
            wx.CallAfter(self.PostInit)
            return True
            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False


    def PostInit(self):
        try:
            tribler_init(self.utility.getConfigPath(),self.utility.getPath(),self.db_exception_handler)
            self.utility.setTriblerVariables()
            self.utility.postAppInit()
            
            # Singleton for executing tasks that are too long for GUI thread and
            # network thread
            self.guiserver = GUIServer.getInstance()
            self.guiserver.register()
    
            # Singleton for management of user's mugshots (i.e. icons/display pictures)
            self.mm = MugshotManager.getInstance()
            self.mm.register(self.utility.getConfigPath(),self.utility.getPath())

            # H4x0r a bit
            set_tasteheart_bitmaps(self.utility.getPath())
            set_perfBar_bitmaps(self.utility.getPath())
    
            # Put it here so an error is shown in the startup-error popup
            self.serverlistener = ServerListener(self.utility)
            
            # Check webservice for autostart webservice
            #######################################################
            WebListener(self.utility)
            if self.utility.webconfig.Read("webautostart", "boolean"):
                self.utility.webserver.start()
                
            # Start single instance server listenner
            ############################################
            self.serverthread   = Thread(target = self.serverlistener.start)
            self.serverthread.setDaemon(True)
            self.serverthread.setName("SingleInstanceServer"+self.serverthread.getName())
            self.serverthread.start()
    
            self.videoplayer = VideoPlayer.getInstance()
            self.videoplayer.register(self.utility)
            self.videoserver = VideoHTTPServer.getInstance()
            self.videoserver.background_serve()

            notification_init( self.utility )
    
            #self.frame = ABCFrame(-1, self.params, self.utility)
            self.guiUtility = GUIUtility.getInstance(self.utility, self.params)
            updateXRC.main([os.path.join(self.utility.getPath(),'Tribler','vwxGUI')])
            self.res = xrc.XmlResource(os.path.join(self.utility.getPath(),'Tribler','vwxGUI','MyFrame.xrc'))
            self.guiUtility.xrcResource = self.res
            self.frame = self.res.LoadFrame(None, "MyFrame")
            self.guiUtility.frame = self.frame
            self.guiUtility.scrollWindow = xrc.XRCCTRL(self.frame, "level0")
            self.guiUtility.mainSizer = self.guiUtility.scrollWindow.GetSizer()
            self.frame.topBackgroundRight = xrc.XRCCTRL(self.frame, "topBG3")
            self.guiUtility.scrollWindow.SetScrollbars(1,1,1024,768)
            self.guiUtility.scrollWindow.SetScrollRate(15,15)
            self.frame.mainButtonPersons = xrc.XRCCTRL(self.frame, "mainButtonPersons")


            self.frame.numberPersons = xrc.XRCCTRL(self.frame, "numberPersons")
            numperslabel = xrc.XRCCTRL(self.frame, "persons")
            self.frame.numberFiles = xrc.XRCCTRL(self.frame, "numberFiles")
            numfileslabel = xrc.XRCCTRL(self.frame, "files")
            self.frame.messageField = xrc.XRCCTRL(self.frame, "messageField")
            self.frame.firewallStatus = xrc.XRCCTRL(self.frame, "firewallStatus")
            tt = self.frame.firewallStatus.GetToolTip()
            if tt is not None:
                tt.SetTip(self.utility.lang.get('unknownreac_tooltip'))
            
            if sys.platform == "linux2":
                self.frame.numberPersons.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                self.frame.numberFiles.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                self.frame.messageField.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                numperslabel.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
                numfileslabel.SetFont(wx.Font(9,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            """
            searchfilebut = xrc.XRCCTRL(self.frame, "bt257cC")
            searchfilebut.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
            searchpersbut = xrc.XRCCTRL(self.frame, "bt258cC")
            searchpersbut.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)     
            
            self.frame.searchtxtctrl = xrc.XRCCTRL(self.frame, "tx220cCCC")
            """
            
            #self.frame.Refresh()
            #self.frame.Layout()
            self.frame.Show(True)
#===============================================================================
#            global start_time2
#            current_time = time()
#            print "\n\n[StartUpDebug]-----------------------------------------"
#            print "[StartUpDebug]"
#            print "[StartUpDebug]----------- from ABCApp.OnInit ----------Tribler frame is shown after", current_time-start_time2
#            print "[StartUpDebug]"
#            print "[StartUpDebug]-----------------------------------------\n\n"
#===============================================================================
            
            # GUI start
            # - load myFrame 
            # - load standardGrid
            # - gui utility > button mainButtonFiles = clicked
        

            self.Bind(wx.EVT_QUERY_END_SESSION, self.frame.OnCloseWindow)
            self.Bind(wx.EVT_END_SESSION, self.frame.OnCloseWindow)
            
            
            #asked = self.utility.config.Read('askeduploadbw', 'boolean')
            asked = True
            if not asked:
                dlg = BandwidthSelector(self.frame,self.utility)
                result = dlg.ShowModal()
                if result == wx.ID_OK:
                    ulbw = dlg.getUploadBandwidth()
                    self.utility.config.Write('maxuploadrate',ulbw)
                    self.utility.config.Write('maxseeduploadrate',ulbw)
                    self.utility.config.Write('askeduploadbw','1')
                dlg.Destroy()

            # Arno, 2007-05-03: wxWidgets 2.8.3.0 and earlier have the MIME-type for .bmp 
            # files set to 'image/x-bmp' whereas 'image/bmp' is the official one.
            try:
                bmphand = None
                hands = wx.Image.GetHandlers()
                for hand in hands:
                    #print "Handler",hand.GetExtension(),hand.GetType(),hand.GetMimeType()
                    if hand.GetMimeType() == 'image/x-bmp':
                        bmphand = hand
                        break
                #wx.Image.AddHandler()
                if bmphand is not None:
                    bmphand.SetMimeType('image/bmp')
            except:
                # wx < 2.7 don't like wx.Image.GetHandlers()
                print_exc()
            
            # Must be after ABCLaunchMany is created
            self.torrentfeed = TorrentFeedThread.getInstance()
            self.torrentfeed.register(self.utility)
            self.torrentfeed.start()
            
            #print "DIM",wx.GetDisplaySize()
            #print "MM",wx.GetDisplaySizeMM()

            self.torthread = TorThread()
            self.torthread.start()
            
            wx.CallAfter(self.startWithRightView)            
            
        except Exception,e:
            print_exc()
            self.error = e
            self.onError()
            return False

        return True

    def onError(self,source=None):
        # Don't use language independence stuff, self.utility may not be
        # valid.
        msg = "Unfortunately, Tribler ran into an internal error:\n\n"
        if source is not None:
            msg += source
        msg += str(self.error.__class__)+':'+str(self.error)
        msg += '\n'
        msg += 'Please see the FAQ on www.tribler.org on how to act.'
        dlg = wx.MessageDialog(None, msg, "Tribler Fatal Error", wx.OK|wx.ICON_ERROR)
        result = dlg.ShowModal()
        print_exc()
        dlg.Destroy()

    def MacOpenFile(self,filename):
        self.utility.queue.addtorrents.AddTorrentFromFile(filename)

    def OnExit(self):
        
        self.torrentfeed.shutdown()
        self.torthread.shutdown()
        mainlineDHT.deinit()
        
        if not ALLOW_MULTIPLE:
            del self.single_instance_checker
        ClientPassParam("Close Connection")
        return 0
    
    def db_exception_handler(self,e):
        if DEBUG:
            print >> sys.stderr,"abc: Database Exception handler called",e,"value",e.args,"#"
        try:
            if e.args[1] == "DB object has been closed":
                return # We caused this non-fatal error, don't show.
            if self.error is not None and self.error.args[1] == e.args[1]:
                return # don't repeat same error
        except:
            print >> sys.stderr, "abc: db_exception_handler error", e, type(e)
            print_exc()
            #print_stack()
        self.error = e
        self.invokeLater(self.onError,[],{'source':"The database layer reported: "})
    
    def getConfigPath(self):
        return self.utility.getConfigPath()

    def startWithRightView(self):
        if self.params[0] != "":
            self.guiUtility.standardLibraryOverview()
    
        
class DummySingleInstanceChecker:
    
    def __init__(self,basename):
        pass

    def IsAnotherRunning(self):
        "Uses pgrep to find other tribler.py processes"
        # If no pgrep available, it will always start tribler
        progressInfo = commands.getoutput('pgrep -fl tribler.py | grep -v pgrep')
        numProcesses = len(progressInfo.split('\n'))
        if DEBUG:
            print 'ProgressInfo: %s, num: %d' % (progressInfo, numProcesses)
        return numProcesses > 1
                
        
##############################################################
#
# Main Program Start Here
#
##############################################################
def run(params = None):
    global start_time
    start_time = time()
    if params is None:
        params = [""]
    
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    
    # Create single instance semaphore
    # Arno: On Linux and wxPython-2.8.1.1 the SingleInstanceChecker appears
    # to mess up stderr, i.e., I get IOErrors when writing to it via print_exc()
    #
    # TEMPORARILY DISABLED on Linux
    if sys.platform != 'linux2':
        single_instance_checker = wx.SingleInstanceChecker("tribler-" + wx.GetUserId())
    else:
        single_instance_checker = DummySingleInstanceChecker("tribler-")

    #print "[StartUpDebug]---------------- 1", time()-start_time
    if not ALLOW_MULTIPLE and single_instance_checker.IsAnotherRunning():
        #Send  torrent info to abc single instance
        ClientPassParam(params[0])
        #print "[StartUpDebug]---------------- 2", time()-start_time
    else:
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        # Arno: don't chdir to allow testing as other user from other dir.
        #os.chdir(abcpath)

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, abcpath)
        configpath = app.getConfigPath()
#        print "[StartUpDebug]---------------- 3", time()-start_time
        app.MainLoop()

        print "Client shutting down. Sleeping for a few seconds to allow other threads to finish"
        sleep(4)

        # This is the right place to close the database, unfortunately Linux has
        # a problem, see ABCFrame.OnCloseWindow
        #
        #if sys.platform != 'linux2':
        #    tribler_done(configpath)
        os._exit(0)

if __name__ == '__main__':
    run()

