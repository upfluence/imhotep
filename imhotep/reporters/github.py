import logging
from six import string_types
from .reporter import Reporter

log = logging.getLogger(__name__)


class GitHubReporter(Reporter):
    def __init__(self, requester, repo_name):
        self._comments = []
        self.requester = requester
        self.requester_login = requester.get_user().login
        org, repo = repo_name.split('/')
        self.repo = requester.get_organization(org).get_repo(repo)

    def clean_already_reported(self, comments, file_name, position,
                               message):
        """
        message is potentially a list of messages to post. This is later
        converted into a string.
        """
        for comment in comments:
            if (comment.path == file_name and
                comment.user.login == self.requester_login and
                (comment.position == position or
                 comment.original_position == position)):
                return [m for m in message if m not in comment.body]

        return message

    def convert_message_to_string(self, message):
        """Convert message from list to string for GitHub API."""
        final_message = ''
        for submessage in message:
            final_message += '* {submessage}\n'.format(submessage=submessage)
        return final_message


class CommitReporter(GitHubReporter):
    def __init__(self, requester, repo_name, commit):
        super(PRReporter, self).__init__(requester, repo_name)
        self.commit = self.repo.get_commit(commit)

    def report_line(self, commit, file_name, line_number, position, message):
        comments = self.commit.get_comments()
        message = self.clean_already_reported(comments, file_name,
                                              position, message)

        self.commit.create_comment(
            body=self.convert_message_to_string(message),
            commit_id=commit,
            path=file_name,
            position=position)


class PRReporter(GitHubReporter):
    def __init__(self, requester, repo_name, pr_number):
        super(PRReporter, self).__init__(requester, repo_name)
        self.pr = self.repo.get_pull(pr_number)

    def report_line(self, commit, file_name, line_number, position, message):
        comments = self.pr.get_comments()
        if isinstance(message, string_types):
            message = [message]

        message = self.clean_already_reported(comments, file_name,
                                              position, message)

        if not message:
            log.debug('Message already reported')
            return None

        self.pr.create_comment(
            body=self.convert_message_to_string(message),
            commit_id=self.repo.get_commit(commit),
            path=file_name,
            position=position)

    def post_comment(self, message):
        """
        Comments on an issue, not on a particular line.
        """
        self.pr.create_issue_comment(message)

    def pre_report(self):
        commit = self.pr.head.repo.get_commit(self.pr.head.sha)
        commit.create_status('pending', description='Checking the style',
                             context='linter/imhotep')

    def post_report(self, violations):
        if violations > 0:
            status = 'failure'
            description = 'The linting failed'
        else:
            status = 'success'
            description = 'The linting passed'

        commit = self.pr.head.repo.get_commit(self.pr.head.sha)
        commit.create_status(status, description=description,
                             context='linter/imhotep')
