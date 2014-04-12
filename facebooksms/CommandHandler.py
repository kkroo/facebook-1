from facebooksms import *

class CommandError(RuntimeError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class CommandHandler(object):

    """
    The command handler performs authentication and basic syntax checking for
    commands. We dispatch the command to the right handler, then check whether
    or not the issuer of the command is authorized to execute it. We also
    verify the command has the right number of arguments. The semantics of each
    command should be implemented elsewhere -- we'll check whether or not the
    command is semantically valid where it's defined.

    If command handling fails at any point, we raise a CommandError. The value
    of the exception should be sent as a reply by the calling application.

    TODO: we really should validate arguments here (should all be ints).
    """
    def __init__(self, app):
        self.app = app
        self.conf = app.conf
        self.commands = {"friend": self.find_friend,
                         "help":   self.cmd_help,
                         "wall":   self.wall_info,
                         "unsubscribe": self.unsubscribe
                        }

    app_commands = ["friend", "wall", "unsubscribe"]

    def dispatch(self, message, cmd, arguments):
        """ Dispatch a command to the appropriate handler. We check to make
        sure the command exists and is directed to a valid number before
        dispatching.
        """
        # case insensitive -- lowercase is impossible in T9-land!
        cmd = cmd.lower()

        # Don't dispatch non-commands
        if not cmd in self.commands:
            e = "The command '%s' doesn't exist. Try sending 'help' to %s." \
                % (cmd, self.conf.app_number)
            raise CommandError(e)

        # Check if an app number command was sent to the right place
        recp = message.recipient
        app_number = str(self.conf.app_number)
        if cmd in CommandHandler.app_commands and not recp == app_number:
            e = "The command '%s' must be sent to %s." % (cmd, app_number)
            raise CommandError(e)
        elif cmd == "help":
            pass # we'd fail on the next check with this so we special case it
        elif not cmd in CommandHandler.app_commands and recp == app_number:
            e = "The command '%s' must be sent directly to a Facebook wall." % (cmd)
            raise CommandError(e)

        if not arguments:
            arguments = []

        handler_func = self.commands[cmd]
        handler_func(message, cmd, arguments)

    def looks_like_command(self, message):
        body = message.body
        cmd = body.split()[0].lower()

        # dispatch() will verify the command actually exists and is sent to the
        # proper number. The goal here is to accept anything that looks like it
        # could have been intended as a command, and then deliver an
        # appropriate error to the user if the command turns out to be
        # malformed.
        is_to_app = str(message.recipient) == str(self.conf.app_number)
        return is_to_app or cmd in self.commands.keys()

    def invalid_command(self, command):
        if not command:
            e = "Invalid command. Send 'help' to %s for a list of commands." \
                % (self.conf.app_number)
        else:
            e = "Invalid command. Send 'help %s' to %s for info." % \
                (command, self.conf.app_number)
        raise CommandError(e)

    def find_friend(self, message, cmd, args):
        """
        This command is sent to the application.
        Uses this command to retrieve the "numbers" of 
        friends matching a search query
        """
        if not len(args) > 0:
            self.invalid_command("friend")

        q = ' '.join(args)
        self.app.find_friend(q)

    def unsubscribe(self, message, cmd, args):
        self.app.unsubscribe()

    def wall_info(self, message, cmd, args):
        self.app.wall_info()

    def cmd_help(self, message, cmd, args):
        """
        This command is sent directly to a list or to the application.
        Anyone can ask for help. Should return a list of commands, and if
        there's an argument, should show help for specified command.
        """
        help_strings = {
                        "help": "For more info send 'help <command>' to %s. Available commands: %s." % (self.conf.app_number, ", ".join(self.commands.keys())),
                        "friend" : "Send 'friend <name>' to %s to find the number to SMS to send a Facebook message to a friend." % self.conf.app_number,
                        "wall":  "Send 'wall' to view the SMS number of your news feed."
    }
        if cmd == "help":
            if not args or len(args) == 0:
                help_cmd = "help"
            else:
                help_cmd = args[0]
            if help_cmd in help_strings:
                raise CommandError(help_strings[help_cmd])
        raise CommandError(help_strings["help"])

