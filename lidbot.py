#!/usr/bin/env python

# import twisted
from twisted.words.protocols import irc
from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import Factory

import time, sys, re, ConfigParser, yaml

from pprint import pprint
from collections import namedtuple

class Core:
  def __init__(self):
    self.version = "LidBot (core v1.0)"
    self.managers = {}
    self.irc_clients = {}
    self.config = {}

  def start(self):
    reactor.run()

  def stop(self):
    reactor.stop()

  def loadConfig(self):
    config_file = file('cfg/config.yml', 'r')
    self.config = yaml.load(config_file)

  def saveConfig(self):
    config_file = file('cfg/config.yml', 'w')
    yaml.dump(self.config, config_file)

  def doStartup(self):
    self.loadConfig()
    manager_config = self.config['manager']
    client_config = self.config['client']
    # start manager
    self.addManager(manager_config['port'], manager_config['username'], manager_config['password'])
    # start clients
    for client in client_config.keys():
      self.addIRCClient(client, client_config[client]['address'], client_config[client]['port'], client_config[client]['username'], client_config[client]['nickname'], client_config[client]['password'])
      if client_config[client]['enabled'] == True:
        self.startIRCClient(client)
      else:
        print "client", client, "is disabled"

  def addManager(self, port, username, password):
    manager = LidBotManagerFactory(self)
    reactor.listenTCP(54321, manager)

  def addIRCClient(self, name, address, port, username, nickname, password=""):
    print "Adding IRC client"
    server = namedtuple('IRCServer', 'factory, client, conn, address, port, username, nickname, password, channels, signed_on')
    factory = LidBotIRCClientFactory(self, name, nickname, password)
    server.address = address
    server.port = port
    server.username = username
    server.nickname = nickname
    server.password = password
    server.factory = factory
    server.channels = {}
    self.irc_clients[name] = server

  def startIRCClient(self, name):
    server = self.irc_clients[name]
    server.conn = reactor.connectTCP(server.address, server.port, server.factory)

  def enableIRCClient(self, name):
    print "Enabling IRC client", name
    if name in self.config['client']:
      if self.config['client'][name]['enabled'] == True:
        print "Already enabled"
      else:
        self.config['client'][name]['enabled'] = True
        self.startIRCClient(name)
    else:
      print "Not found in config"
        
  def disableIRCClient(self, name):
    print "Disabling IRC client", name
    if name in self.config['client']:
      if self.config['client'][name]['enabled'] == False:
        print "Already disabled"
      else:
        self.config['client'][name]['enabled'] = False
        self.stopIRCClient(name)
    else:
      print "Not found in config"

  def stopIRCClient(self, name):
    server = self.irc_clients[name]
    server.factory.client.quit
    server.conn.disconnect()

  def addIRCClientToChannel(self, client_name, channel_name):
    server = self.irc_clients[client_name]
    server.factory.client.join(channel_name)
    self.config['client'][client_name]['channel'][channel_name] = {'enabled': True}

  def removeIRCClientFromChannel(self, client_name, channel_name):
    server = self.irc_clients[client_name]
    server.factory.client.leave(channel_name)

  def sendIRCClientMessage(self, client_name, destination, message):
    server = self.irc_clients[client_name]
    print "Sending", message, "to", destination, "on", client_name
    server.factory.client.msg(destination, message)

  def sendIRCClientAction(self, client_name, destination, message):
    server = self.irc_clients[client_name]
    server.factory.client.me(destination, message)
    

class LidBotIRCClient(irc.IRCClient):
  """LidBot"""

  def __init__(self, core, name, nickname, password):
    print "LidBot IRCClient loaded"
    self.core = core
    self.name = name
    self.nickname = nickname
    self.password = password
    print "IRCClient: ", self.core.version
    print "Nickname: ", self.nickname, "Password:", self.password

  def connectionMade(self):
    self.factory.client = self
    irc.IRCClient.connectionMade(self)
    print "Connection made"
  
  def connectionLost(self, reason):
    self.factory.client = None
    irc.IRCClient.connectionLost(self, reason)
    print "Connection lost"

  def connected(self):
    pass

  def signedOn(self):
    print "Successfully signed on to", self.name
    self.core.irc_clients[self.name].signed_on = True
    
    # log onto all channels
    for channel in self.core.config['client'][self.name]['channel'].keys():
      if self.core.config['client'][self.name]['channel'][channel]['enabled'] == True:
        self.core.addIRCClientToChannel(self.name, channel)

  def joined(self, joined):
    pass

  def privmsg(self, user, channel, msg):
    print user, channel, msg
    pass
  
  def action(self, user, channel, msg):
    pass

class LidBotManager(LineReceiver):
  def __init__(self, core):
    print "LidBot Manager loaded"
    self.prompt = "lidbot> "
    self.server = {}
    #self.addServer('192.168.16.2', 6667, bot)
    self.core = core
    print "Manager: ", self.core.version

  def connectionMade(self):
    self.sendLine("Connected to LidBot Manager.")
    self.transport.write(self.prompt)

  def lineReceived(self, line):
    print "Manager: Line received: ", line
    if line:
      cmd = line.split()
      if cmd[0] == "save":
        self.core.saveConfig()
        print "Config saved"
        self.transport.write("Config saved\n")
      elif cmd[0] == "client":
        if len(cmd) > 1:
          if cmd[1] == "list":
            for client in self.core.irc_clients:
              self.transport.write(client + '\n')
          elif cmd[1] == "connect":
            print len(cmd)
            if len(cmd) > 2:
              if cmd[2] in self.core.irc_clients:
                self.core.startIRCClient(cmd[2])
              else:
                self.transport.write("Unknown client '" + cmd[2] + "'")
            else:
              self.transport.write("Missing client name\n")
          elif cmd[1] == "disconnect":
            if len(cmd) > 2:
              if cmd[2] in self.core.irc_clients:
                self.core.stopIRCClient(cmd[2])
              else:
                self.transport.write("Unknown client '" + cmd[2] + "'")
            else:
              self.transport.write("Missing client name\n")
          elif cmd[1] == "disable":
            if len(cmd) > 2:
              self.core.disableIRCClient(cmd[2])
          elif cmd[1] == "enable":
            if len(cmd) > 2:
              self.core.enableIRCClient(cmd[2])
          elif cmd[1] == "join":
            if len(cmd) > 3:
              if cmd[2] in self.core.irc_clients:
                self.core.addIRCClientToChannel(cmd[2], cmd[3])
              else:
                self.transport.write("Unknown client '" + cmd[2] + "'")
            else:
              self.transport.write("Missing client name\n")
          elif cmd[1] == "leave":
            if len(cmd) > 3:
              if cmd[2] in self.core.irc_clients:
                self.core.removeIRCClientFromChannel(cmd[2], cmd[3])
              else:
                self.transport.write("Unknown client '" + cmd[2] + "'")
            else:
              self.transport.write("Missing client name\n")
          elif cmd[1] == "announce":
            if len(cmd) > 3:
              if cmd[2] in self.core.irc_clients:
                self.core.sendIRCClientMessage(cmd[2], '#' + cmd[3], "I am LidBot!")
                #self.core.sendIRCClientAction(cmd[2], cmd[3], "dances")
              else:
                self.transport.write("Unknown client '" + cmd[2] + "'")
            else:
              self.transport.write("Missing client name\n")
        else:
          self.transport.write("Missing client sub-command\n")

    self.transport.write(self.prompt)

class LidBotIRCClientFactory(protocol.ClientFactory):
  """Factory class for LidBots"""

  def __init__(self, core, name, nickname, password):
    self.core = core
    self.name = name
    self.client = None
    self.nickname = nickname
    self.password = password
  
  def buildProtocol(self, address):
    protocol = LidBotIRCClient(self.core, self.name, self.nickname, self.password)
    protocol.factory = self
    return protocol

  def connectionLost(self, connector, reason):
    connector.connect()

  def connectionFailed(self, connector, reason):
    reactor.stop()

class LidBotManagerFactory(protocol.ClientFactory):
  def __init__(self, core):
    self.core = core

  def buildProtocol(self, address):
    protocol = LidBotManager(self.core)
    protocol.factory = self
    return protocol

if __name__ == '__main__':
  core = Core()
  core.doStartup()
  core.start()
