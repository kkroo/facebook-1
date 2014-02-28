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
        self.commands = {"password": self.update_password,
                        }

    app_commands = ["password"]

    def dispatch(self, message, cmd, arguments, confirmed):
        """ Dispatch a command to the appropriate handler. We check to make
        sure the command exists and is directed to a valid number before
        dispatching.
        """
        # case insensitive -- lowercase is impossible in T9-land!
        cmd = cmd.lower()

        # Don't dispatch non-commands
        if not cmd in self.commands:
            e = "The command '%s' doesn't exist. Try sending 'help' to %s, or call 411 for Information." \
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
        handler_func(message, cmd, arguments, confirmed)

    def looks_like_command(self, message):
        body = message.body
        has_cmd_char = body.startswith(self.conf.cmd_char)
        if has_cmd_char:
            cmd = body[1:].split()[0].lower()
        elif len(body.split()) >= 1:
            cmd = body.split()[0].lower()
        else:
            return False

        # dispatch() will verify the command actually exists and is sent to the
        # proper number. The goal here is to accept anything that looks like it
        # could have been intended as a command, and then deliver an
        # appropriate error to the user if the command turns out to be
        # malformed.
        is_to_app = str(message.recipient) == str(self.conf.app_number)
        return is_to_app or has_cmd_char or cmd in self.commands.keys()

    def invalid_command(self, command):
        if not command:
            e = "Invalid command. Send 'help' to %s for a list of commands." \
                % (self.conf.app_number)
        else:
            e = "Invalid command. Send 'help %s' to %s for info." % \
                (command, self.conf.app_number)
        raise CommandError(e)

    def update_password(self, message, cmd, args):
        """
        This command is sent to the application.
        If list creation is enabled, anyone can create lists.
        """
        if not len(args) == 1:
            self.invalid_command("create")

        l = List(args[0], self.app)
        l.create(message.sender)

    def cmd_help(self, message, cmd, args, confirmed):
        """
        This command is sent directly to a list or to the application.
        Anyone can ask for help. Should return a list of commands, and if
        there's an argument, should show help for specified command.
        """
        help_strings = {
                        "help": "For more info send 'help <command>' to %s. Available commands: %s. More questions? Call 411." % (self.conf.app_number, ", ".join(self.commands.keys())),
                        "password" : "Send 'password <your password>' to %s to update your saved password." % self.conf.app_number
    }
        if cmd == "help":
            if not args or len(args) == 0:
                help_cmd = "help"
            else:
                help_cmd = args[0]
            if help_cmd in help_strings:
                raise CommandError(help_strings[help_cmd])
        raise CommandError(help_strings["help"])

