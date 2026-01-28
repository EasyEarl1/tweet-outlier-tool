"""
Tweet Outlier Tool - Main CLI Interface
"""
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from database import Database
from account_importer import AccountImporter
from twitter_api import TwitterAPI
from data_fetcher import DataFetcher
from analyzer import TweetAnalyzer
from datetime import datetime
import os

console = Console()


@click.group()
def cli():
    """Tweet Outlier Tool - Find tweets that outperformed the norm"""
    pass


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--type', 'file_type', default='auto', help='File type: csv, txt, or auto')
@click.option('--column', 'username_column', default='username', help='Username column name for CSV')
def import_accounts(file_path, file_type, username_column):
    """Import accounts from a CSV or TXT file"""
    console.print(f"[bold blue]Importing accounts from {file_path}...[/bold blue]")
    
    db = Database()
    importer = AccountImporter(db)
    
    try:
        imported, errors = importer.import_accounts(file_path, file_type, username_column)
        
        console.print(f"[green]✓ Successfully imported {imported} accounts[/green]")
        
        if errors:
            console.print(f"[yellow]⚠ {len(errors)} errors occurred:[/yellow]")
            for error in errors[:10]:  # Show first 10 errors
                console.print(f"  - {error}")
            if len(errors) > 10:
                console.print(f"  ... and {len(errors) - 10} more errors")
    except Exception as e:
        console.print(f"[red]✗ Error: {str(e)}[/red]")
        raise click.Abort()


@cli.command()
@click.option('--months', default=3, type=click.IntRange(1, 6), help='Number of months to fetch (1-6)')
@click.option('--delay', default=2, type=float, help='Delay between accounts in seconds')
def fetch(months, delay):
    """Fetch tweets for all accounts in the database"""
    console.print(f"[bold blue]Fetching tweets for all accounts...[/bold blue]")
    console.print(f"[dim]Time range: Last {months} months[/dim]\n")
    
    try:
        db = Database()
        twitter_api = TwitterAPI()
        fetcher = DataFetcher(db, twitter_api)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching data...", total=None)
            results = fetcher.fetch_all_accounts(months_back=months, delay_between_accounts=delay)
        
        # Display results
        console.print("\n[bold green]Fetch Complete![/bold green]\n")
        console.print(f"Total accounts: {results['total_accounts']}")
        console.print(f"Successful: [green]{results['successful']}[/green]")
        console.print(f"Failed: [red]{results['failed']}[/red]")
        console.print(f"Total tweets fetched: [cyan]{results['total_tweets']}[/cyan]")
        
        if results['errors']:
            console.print("\n[yellow]Errors:[/yellow]")
            for error in results['errors']:
                console.print(f"  - {error}")
    
    except ValueError as e:
        console.print(f"[red]✗ Configuration error: {str(e)}[/red]")
        console.print("[yellow]Make sure TWITTER_API_KEY is set in .env file[/yellow]")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]✗ Error: {str(e)}[/red]")
        raise click.Abort()


@cli.command()
@click.option('--months', default=3, type=click.IntRange(1, 6), help='Number of months to analyze (1-6)')
@click.option('--threshold', default=2.0, type=float, help='Minimum multiplier to be considered an outlier')
@click.option('--account', 'account_username', default=None, help='Analyze specific account only')
def analyze(months, threshold, account_username):
    """Analyze tweets and calculate outlier multipliers"""
    console.print(f"[bold blue]Analyzing tweets...[/bold blue]")
    console.print(f"[dim]Time range: Last {months} months | Outlier threshold: {threshold}x[/dim]\n")
    
    db = Database()
    analyzer = TweetAnalyzer(db)
    
    if account_username:
        # Analyze single account
        account = db.get_account(account_username.lstrip('@'))
        if not account:
            console.print(f"[red]✗ Account @{account_username} not found in database[/red]")
            raise click.Abort()
        
        console.print(f"Analyzing @{account.username}...")
        result = analyzer.analyze_account(account.id, months, threshold)
        result['username'] = account.username
        
        _display_analysis_result(result, threshold)
    else:
        # Analyze all accounts
        console.print("Analyzing all accounts...\n")
        results = analyzer.analyze_all_accounts(months, threshold)
        
        # Display summary
        _display_summary(results, threshold)
        
        # Display top outliers
        _display_top_outliers(db, threshold)


def _display_analysis_result(result, threshold):
    """Display analysis result for a single account"""
    if 'error' in result:
        console.print(f"[red]✗ {result['error']}[/red]")
        return
    
    account_avg = result['account_avg']
    
    console.print(f"\n[bold]@{result['username']}[/bold]")
    console.print(f"Total tweets analyzed: {result['total_tweets']}")
    console.print(f"Outliers found: [cyan]{result['outlier_count']}[/cyan] (≥{threshold}x average)\n")
    
    console.print("[dim]Account Averages:[/dim]")
    console.print(f"  Engagement Score: {account_avg['avg_engagement']:.2f}")
    console.print(f"  Likes: {account_avg['avg_likes']:.1f}")
    console.print(f"  Retweets: {account_avg['avg_retweets']:.1f}")
    console.print(f"  Replies: {account_avg['avg_replies']:.1f}")
    console.print(f"  Views: {account_avg['avg_views']:.0f}\n")
    
    if result['outliers']:
        table = Table(title=f"Top Outliers for @{result['username']}")
        table.add_column("Multiplier", style="cyan", justify="right")
        table.add_column("Likes", justify="right")
        table.add_column("Retweets", justify="right")
        table.add_column("Replies", justify="right")
        table.add_column("Views", justify="right")
        table.add_column("Text", style="dim", max_width=50)
        
        for outlier in result['outliers'][:10]:  # Top 10
            table.add_row(
                f"{outlier['multiplier']:.2f}x",
                str(outlier['likes']),
                str(outlier['retweets']),
                str(outlier['replies']),
                str(outlier['views']),
                outlier['text']
            )
        
        console.print(table)
    else:
        console.print("[yellow]No outliers found above the threshold[/yellow]")


def _display_summary(results, threshold):
    """Display summary of analysis across all accounts"""
    total_accounts = len(results)
    accounts_with_outliers = sum(1 for r in results if r.get('outlier_count', 0) > 0)
    total_outliers = sum(r.get('outlier_count', 0) for r in results)
    
    console.print(f"\n[bold green]Analysis Complete![/bold green]\n")
    console.print(f"Accounts analyzed: {total_accounts}")
    console.print(f"Accounts with outliers: [cyan]{accounts_with_outliers}[/cyan]")
    console.print(f"Total outliers found: [cyan]{total_outliers}[/cyan] (≥{threshold}x average)\n")


def _display_top_outliers(db, threshold, limit=20):
    """Display top outliers across all accounts"""
    outliers = db.get_outlier_tweets(min_multiplier=threshold, limit=limit)
    
    if not outliers:
        console.print("[yellow]No outliers found[/yellow]")
        return
    
    table = Table(title=f"Top {len(outliers)} Outliers Across All Accounts")
    table.add_column("Account", style="bold")
    table.add_column("Multiplier", style="cyan", justify="right")
    table.add_column("Likes", justify="right")
    table.add_column("Retweets", justify="right")
    table.add_column("Replies", justify="right")
    table.add_column("Views", justify="right")
    table.add_column("Text", style="dim", max_width=40)
    
    for tweet in outliers:
        table.add_row(
            f"@{tweet.account.username}",
            f"{tweet.outlier_multiplier:.2f}x",
            str(tweet.likes),
            str(tweet.retweets),
            str(tweet.replies),
            str(tweet.views),
            (tweet.text[:40] + '...') if tweet.text and len(tweet.text) > 40 else (tweet.text or '')
        )
    
    console.print(table)


@cli.command()
def list_accounts():
    """List all accounts in the database"""
    db = Database()
    accounts = db.get_all_accounts()
    
    if not accounts:
        console.print("[yellow]No accounts in database. Use 'import-accounts' to add some.[/yellow]")
        return
    
    table = Table(title=f"Accounts in Database ({len(accounts)})")
    table.add_column("Username", style="bold")
    table.add_column("Display Name", style="dim")
    table.add_column("Followers", justify="right")
    table.add_column("Last Updated", style="dim")
    
    for account in accounts:
        last_updated = account.last_updated.strftime("%Y-%m-%d") if account.last_updated else "Never"
        table.add_row(
            f"@{account.username}",
            account.display_name or "-",
            f"{account.follower_count:,}" if account.follower_count else "-",
            last_updated
        )
    
    console.print(table)


@cli.command()
def stats():
    """Show database statistics"""
    db = Database()
    accounts = db.get_all_accounts()
    
    total_tweets = 0
    total_outliers = 0
    
    for account in accounts:
        tweets = db.get_tweets_by_account(account.id)
        total_tweets += len(tweets)
        total_outliers += sum(1 for t in tweets if t.is_outlier)
    
    console.print(Panel.fit(
        f"[bold]Database Statistics[/bold]\n\n"
        f"Accounts: [cyan]{len(accounts)}[/cyan]\n"
        f"Total Tweets: [cyan]{total_tweets:,}[/cyan]\n"
        f"Outliers: [cyan]{total_outliers:,}[/cyan]",
        title="Stats"
    ))


@cli.command()
def web():
    """Start the web UI server"""
    import subprocess
    import sys
    console.print("[bold blue]Starting web UI server...[/bold blue]")
    console.print("[dim]Open http://localhost:5000 in your browser[/dim]\n")
    subprocess.run([sys.executable, "app.py"])


if __name__ == '__main__':
    cli()

