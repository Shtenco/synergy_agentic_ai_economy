// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;

contract TestToken {
    string public name; string public symbol; uint8 public immutable decimals;
    uint256 public totalSupply; address public owner;
    mapping(address=>bool) public minter;
    mapping(address=>uint256) public balanceOf;
    mapping(address=>mapping(address=>uint256)) public allowance;
    event Transfer(address indexed from,address indexed to,uint256 value);
    event Approval(address indexed owner,address indexed spender,uint256 value);
    modifier onlyOwner(){require(msg.sender==owner,"OWNER");_;}
    modifier onlyMinter(){require(minter[msg.sender],"MINTER");_;}
    constructor(string memory n,string memory s,uint8 d){name=n;symbol=s;decimals=d;owner=msg.sender;minter[msg.sender]=true;}
    function setMinter(address a,bool on) external onlyOwner{minter[a]=on;}
    function approve(address s,uint256 v) external returns(bool){allowance[msg.sender][s]=v;emit Approval(msg.sender,s,v);return true;}
    function transfer(address to,uint256 v) external returns(bool){_transfer(msg.sender,to,v);return true;}
    function transferFrom(address f,address t,uint256 v) external returns(bool){uint256 a=allowance[f][msg.sender];require(a>=v,"ALLOW");if(a!=type(uint256).max)allowance[f][msg.sender]=a-v;_transfer(f,t,v);return true;}
    function mint(address to,uint256 v) external onlyMinter{totalSupply+=v;balanceOf[to]+=v;emit Transfer(address(0),to,v);}
    function burn(uint256 v) external{require(balanceOf[msg.sender]>=v,"BAL");balanceOf[msg.sender]-=v;totalSupply-=v;emit Transfer(msg.sender,address(0),v);}
    function _transfer(address f,address t,uint256 v) internal{require(t!=address(0),"ZERO");require(balanceOf[f]>=v,"BAL");balanceOf[f]-=v;balanceOf[t]+=v;emit Transfer(f,t,v);}
}
